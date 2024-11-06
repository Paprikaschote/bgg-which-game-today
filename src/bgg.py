import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union

from bs4 import BeautifulSoup

from .db import Database
from .models import Category, Game, Mechanism, Type
from .selenium import Selenium


class BGG:
    def __init__(self, bgg_username: str, verbose: bool = False):
        self.bgg_domain = "https://boardgamegeek.com"
        self.bgg_username = bgg_username
        self.games = []
        self.verbose = verbose

    def check(self, soup: BeautifulSoup) -> Union[Exception, None]:
        error = soup.find("div", class_="messagebox error")
        if error and error.text.strip() == "No username specified.":
            raise Exception("Wrong BGG username")

    def get_data_from_collection(self) -> None:
        bgg_collection_url = f"https://boardgamegeek.com/collection/user/{self.bgg_username}?own=1&subtype=boardgame&ff=1"
        rendered_html = Selenium(bgg_collection_url).get_html_content()
        soup = BeautifulSoup(rendered_html, "html.parser")

        self.check(soup)

        table = soup.find("table", {"id": "collectionitems"})
        game_urls = [
            (
                a_tag["href"].split("/")[2],
                a_tag.text,
                f"{self.bgg_domain}{a_tag['href']}",
            )
            for tr in table.find_all("tr", id=lambda x: x and x.startswith("row_"))
            if (a_tag := tr.find("a", class_="primary"))
        ]

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self._get_data_from_detail_page, bgg_id, name, bgg_url)
                for bgg_id, name, bgg_url in game_urls
            ]
            for future in as_completed(futures):
                future.result()

    def _extract_links_for_category(
        self, items: BeautifulSoup, category_name: str
    ) -> Union[List[Type], List[Category], List[Mechanism]]:
        classifications = []
        class_map = {"type": Type, "category": Category, "mechanism": Mechanism}
        for link in items.find_all("a", href=True):
            bgg_id = link["href"].split("/")[2]
            classification = Database().get_classification_by_id(
                bgg_id, category_name.lower()
            )
            classification_class = class_map.get(category_name.lower())
            if classification:
                classifications.append(
                    classification_class(
                        classification["bgg_id"],
                        classification["name"],
                        classification["bgg_url"],
                        classification["description"],
                    )
                )
                if self.verbose:
                    print(f"Known {category_name}: {classification['name']}")
                continue

            bgg_url = f"{self.bgg_domain}{link['href']}"
            rendered_html = Selenium(bgg_url).get_html_content()
            if rendered_html:
                soup = BeautifulSoup(rendered_html, "html.parser")

                name = link.text.strip()
                description = soup.find("meta", attrs={"name": "description"})
                if classification_class:
                    classifications.append(
                        classification_class(
                            bgg_id,
                            re.sub(
                                r"[:,]", "/", name
                            ),  # replace ":" and "," due to needs of Database.get_games()
                            bgg_url,
                            description=description.get("content"),
                        )
                    )
                    if self.verbose:
                        print(f"New {category_name}: {name}")
        return classifications

    def _get_data_from_detail_page(self, bgg_id: int, title: str, bgg_url: str) -> Game:
        if self.verbose:
            print(f"Getting data from {bgg_url}")
        rendered_html = Selenium(bgg_url).get_html_content()
        soup = BeautifulSoup(rendered_html, "html.parser")

        game = Game(bgg_id=bgg_id, bgg_url=bgg_url, title=title)

        expansion = soup.find("div", class_="game-header-subtype ng-scope")
        game.expansion = bool(expansion and "Expansion" in expansion.get_text())

        description = soup.find("article", class_="game-description-body")
        if description:
            game.description = description.get_text(separator="\n").strip()

        year = soup.find("span", class_="game-year")
        if year:
            match = re.search(r"\d{4}", year.text)
            if match:
                game.year = match.group(0)

        bgg_rating = soup.find("span", itemprop="ratingValue")
        if bgg_rating:
            game.bgg_rating = bgg_rating.text.strip()

        complexity = soup.find("span", {"class": re.compile("gameplay-weight-.*")})
        if complexity:
            game.complexity = complexity.text.strip()

        players = soup.find("li", itemprop="numberOfPlayers")
        if players:
            min_players = players.find("meta", itemprop="minValue")
            max_players = players.find("meta", itemprop="maxValue")
            game.min_players = min_players["content"] if min_players else None
            game.max_players = max_players["content"] if max_players else None

        game.min_playtime = 0
        game.max_playtime = 0
        gameplay_items = soup.find_all("li", class_="gameplay-item")
        for gameplay_item in gameplay_items:
            play_time = gameplay_item.find("h3", string="Play Time")
            if play_time:
                min_playtime = gameplay_item.find(
                    "span",
                    class_="ng-binding ng-scope",
                )
                if min_playtime:
                    game.min_playtime = min_playtime.get_text(strip=True)
                    max_playtime = min_playtime.find_next_sibling()
                    if max_playtime:
                        game.max_playtime = (
                            max_playtime.get_text(strip=True).split("–")[-1].strip()
                        )
                    else:
                        game.max_playtime = game.min_playtime
                break

        image = soup.find("img", itemprop="image")
        if image:
            game.image_url = image["src"]

        game_classification = soup.find("div", class_="game-classification")
        if game_classification:
            category = game_classification.find("h4", text=re.compile("Type"))
            if category:
                feature_item = category.find_parent("li")
                if feature_item:
                    game.types = self._extract_links_for_category(feature_item, "Type")

        # new request due to details like "+ 5 more"
        bgg_url = f"{bgg_url}/credits"
        rendered_html = Selenium(bgg_url).get_html_content()
        soup = BeautifulSoup(rendered_html, "html.parser")

        game_classification = soup.find_all("li", class_="outline-item ng-scope")
        for element in game_classification:
            title_element = element.find("span", id="fullcredits-boardgamecategory")
            if title_element:
                game.categories = self._extract_links_for_category(element, "Category")

            title_element = element.find("span", id="fullcredits-boardgamemechanic")
            if title_element:
                game.mechanisms = self._extract_links_for_category(element, "Mechanism")

        self.games.append(game)
