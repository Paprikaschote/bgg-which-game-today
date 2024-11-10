from typing import Dict, List


class Classification:
    def __init__(
        self, bgg_id: int, name: str, bgg_url: str = None, description: str = None
    ):
        self.bgg_id = bgg_id
        self.name = name
        self.bgg_url = bgg_url
        self.description = description

    def to_dict(self) -> Dict:
        return {
            "bgg_id": self.bgg_id,
            "name": self.name,
            "bgg_url": self.bgg_url,
            "description": self.description,
        }

    def __str__(self):
        return self.name

    def get_type(self) -> str:
        return "Classification"


class Category(Classification):
    def get_type(self) -> str:
        return "Category"


class Type(Classification):
    def get_type(self) -> str:
        return "Type"


class Mechanism(Classification):
    def get_type(self) -> str:
        return "Mechanism"


class Game:
    def __init__(
        self,
        bgg_id: int,
        title: str,
        description: str = None,
        year: int = None,
        bgg_rating: float = None,
        complexity: float = None,
        bgg_url: str = None,
        image_url: str = None,
        min_players: int = None,
        max_players: int = None,
        min_playtime: int = None,
        max_playtime: int = None,
        types: List[Type] = None,
        categories: List[Category] = None,
        mechanisms: List[Mechanism] = None,
    ):
        self.bgg_id = bgg_id
        self.title = title
        self.description = description
        self.year = year
        self.bgg_rating = bgg_rating
        self.complexity = complexity
        self.bgg_url = bgg_url
        self.image_url = image_url
        self.min_players = min_players
        self.max_players = max_players
        self.min_playtime = min_playtime
        self.max_playtime = max_playtime
        self.types = types if types is not None else []
        self.categories = categories if categories is not None else []
        self.mechanisms = mechanisms if mechanisms is not None else []

    @property
    def data_for_vectorization(self) -> str:
        data = self.types + self.categories + self.mechanisms
        return ", ".join([item.name for item in data])

    def to_dict(self, show_description: bool = True) -> Dict:
        game_dict = {
            "bgg_id": self.bgg_id,
            "title": self.title,
            "year": self.year,
            "bgg_rating": self.bgg_rating,
            "complexity": self.complexity,
            "bgg_url": self.bgg_url,
            "image_url": self.image_url,
            "min_players": self.min_players,
            "max_players": self.max_players,
            "min_playtime": self.min_playtime,
            "max_playtime": self.max_playtime,
            "types": [game_type.name for game_type in self.types],
            "categories": [category.name for category in self.categories],
            "mechanisms": [mechanism.name for mechanism in self.mechanisms],
        }
        if show_description:
            game_dict["description"] = self.description
        return game_dict
