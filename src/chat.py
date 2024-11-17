import json
import os
import sys
from typing import Literal, Union

import requests
from openai import OpenAI
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from .db import Database
from .qdrant import Qdrant

NO_GAME_FOUND_MSG = "No suitable game models were found based on your request."


class Chat:
    use_openai = os.environ.get("USE_OPENAI", False) == "True"
    gpt_chat_model = os.environ.get("GPT_CHAT_MODEL", "gpt-4o-mini")
    local_chat_model = os.environ.get("LOCAL_CHAT_MODEL", "llama-3.2-1b-instruct:q8_0")

    def __init__(self, vebrose: bool = False):
        self.openai_client = None
        self.chat_history = []
        self.verbose = vebrose

    def check(self):
        if self.use_openai and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("Missing OpenAI API key. Set OPENAI_API_KEY to proceed")

    def append_chat_history(
        self, role: Union[Literal["user"], Literal["system"]], content: str
    ):
        self.chat_history.append({"role": role, "content": content})

    def execute(self) -> str:
        response_content = ""

        if self.use_openai:
            if not self.openai_client:
                self.openai_client = OpenAI()
            completion = self.openai_client.chat.completions.create(
                model=self.gpt_chat_model,
                messages=self.chat_history,
                temperature=0.0,
                stream=True,
            )
            for chunk in completion:
                delta = chunk.choices[0].delta
                if delta.content:
                    response_content += delta.content
        else:
            url = "http://localhost:8080/v1/chat/completions"
            headers = {"content-type": "application/json", "Accept-Charset": "UTF-8"}
            payload = {
                "model": self.local_chat_model,
                "messages": self.chat_history,
                "temperature": 0.0,
            }
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_content = response.json()["choices"][0]["message"]["content"]

        self.chat_history.append({"role": "assistant", "content": response_content})
        return response_content


class PrepareChat(Chat):
    def __init__(
        self, qdrant: Qdrant, model: SentenceTransformer, verbose: bool = False
    ):
        super().__init__(verbose)
        self.qdrant = qdrant
        self.model = model
        self.json_content = {}
        self.filter_players_playtime = []
        self.filter_complexity = []
        self.filter_categories = []

    def get_language(self):
        return self.json_content.get("language", "english")

    def read_filter(self, response_content: str):
        try:
            self.json_content = json.loads(response_content)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            raise json.JSONDecodeError(e)

        for key, value in self.json_content.items():
            if not value:
                continue

            if key == "min_players":
                self.filter_players_playtime.append(
                    models.FieldCondition(
                        key="max_players",
                        range=models.Range(gte=value),
                    )
                )
            elif key == "max_players":
                self.filter_players_playtime.append(
                    models.FieldCondition(
                        key="min_players",
                        range=models.Range(lte=value),
                    )
                )
            elif key == "min_playtime":
                self.filter_players_playtime.append(
                    models.FieldCondition(
                        key="max_playtime",
                        range=models.Range(gte=value),
                    )
                )
            elif key == "max_playtime":
                self.filter_players_playtime.append(
                    models.FieldCondition(
                        key="min_playtime",
                        range=models.Range(lte=value),
                    )
                )
            elif key == "complexity":
                try:
                    min_complexity = float(value) - 1
                    max_complexity = float(value) + 1
                except ValueError as e:
                    if self.verbose:
                        print("Error converting complexity", e)
                    continue
                self.filter_complexity.extend(
                    [
                        models.FieldCondition(
                            key="complexity",
                            range=models.Range(lte=min_complexity, gte=max_complexity),
                        ),
                        models.IsEmptyCondition(
                            is_empty=models.PayloadField(key="complexity"),
                        ),
                    ]
                )
            elif key == "genre":
                self.filter_categories.append(
                    models.FieldCondition(
                        key="type",
                        match=models.MatchAny(any=value),
                    )
                )
                self.filter_categories.append(
                    models.FieldCondition(
                        key="categories",
                        match=models.MatchAny(any=value),
                    )
                )
                self.filter_categories.append(
                    models.FieldCondition(
                        key="mechanism",
                        match=models.MatchAny(any=value),
                    )
                )

    def search_result(self):
        if "genre" in self.json_content:
            query_vector = self.model.encode(
                ", ".join(self.json_content["genre"])
            ).tolist()

            search_result = self.qdrant.client_search(
                query_filter=models.Filter(
                    must=[
                        models.Filter(
                            must=self.filter_players_playtime,
                        ),
                        models.Filter(
                            should=self.filter_complexity,
                        ),
                        models.Filter(
                            should=self.filter_categories,
                        ),
                    ],
                ),
                query_vector=query_vector,
            )
            if not search_result:
                search_result = self.qdrant.client_search(
                    query_filter=models.Filter(
                        must=self.filter_players_playtime,
                        should=[
                            models.Filter(should=self.filter_complexity),
                            models.Filter(should=self.filter_categories),
                        ],
                    ),
                    query_vector=query_vector,
                )

                if not search_result:
                    search_result = self.qdrant.client_search(
                        query_filter=models.Filter(must=self.filter_players_playtime),
                        query_vector=query_vector,
                    )

        else:
            search_result = self.qdrant.client_scroll(
                scroll_filter=models.Filter(
                    must=[
                        models.Filter(
                            must=self.filter_players_playtime,
                        ),
                        models.Filter(
                            should=self.filter_complexity,
                        ),
                        models.Filter(
                            should=self.filter_categories,
                        ),
                    ],
                ),
            )
            if not search_result:
                search_result = self.qdrant.client_scroll(
                    query_filter=models.Filter(
                        must=self.filter_players_playtime,
                        should=[
                            models.Filter(should=self.filter_complexity),
                            models.Filter(should=self.filter_categories),
                        ],
                    ),
                )

                if not search_result:
                    search_result = self.qdrant.client_scroll(
                        query_filter=models.Filter(must=self.filter_players_playtime),
                    )
            search_result = search_result[0]

        if self.verbose:
            print(search_result)
        return search_result


def run(
    db: Database,
    client: QdrantClient,
    model: SentenceTransformer,
    with_expansions: bool = False,
    fast: bool = False,
    verbose: bool = False,
):
    all_games_dict = {game.bgg_id: game for game in db.get_games(with_expansions)}

    qdrant = Qdrant(client, db, model, verbose)
    prepare_chat = PrepareChat(qdrant, model, verbose)
    prepare_chat.check()

    prepare_prompt = """Your sole responsibility is to analyze the user's prompt and extract relevant information to enhance board game search capabilities. Respond exclusively with a JSON object following the schema below, filling in the values based on the user's statement. Do not include any additional text or explanations. If no relevant data is available, remove the key from the json. At the end no None values should be present in the JSON object and the json object must be valid and loadable in the python function json.loads().

    The values for players, playtime, and complexity must be provided as integers only if explicitly mentioned by the user. The playtime must be converted to minutes. The complexity should range from 0 to 5, based on the weight value from boardgamegeeks.com. The language of the user's request must be included in the 'language' key and should be written as an English word. The genre must be a list of values provided in English, and the description should be a flowing text provided in English, regardless of the user's language.

    === SCHEMA
    {
        "min_players": null,
        "max_players": null,
        "min_playtime": null,
        "max_playtime": null,
        "complexity": null,
        "genre": null,
        "language": null
    }
    """

    prepare_chat.append_chat_history("system", prepare_prompt)

    print("What are you looking for today?")
    user_input = input()

    if prepare_chat.use_openai:
        print("Please wait 10 seconds for your game recommendations")
    else:
        print(
            "Please wait up to 2 minutes for your game recommendations. Depends on the gpu / cpu you have"
        )

    prepare_chat.append_chat_history("user", user_input)
    response_content = prepare_chat.execute()

    if verbose:
        print("Prepare Search: ", response_content)

    prepare_chat.read_filter(response_content)

    search_result = prepare_chat.search_result()

    language = prepare_chat.get_language()

    augmented_prompt = f"""You are a board game recommendation assistant. You recommend the games found below GAME RECOMMANDATIONS. Summarize every single entry of games from the GAME RECOMMANDATIONS below in a maximum of two sentences each. If no game under game recommendations are found, apologize and state that no suitable game is available. Answer in {language}.

    === GAME RECOMMANDATIONS

    """

    game_models = []
    for r in search_result:
        if "score" in r and r.score < 0.4:
            continue
        game = all_games_dict.get(r.id)
        if game:
            types = ", ".join([game_type.name for game_type in game.types])
            categories = ", ".join([category.name for category in game.categories])
            mechanisms = ", ".join([mechanism.name for mechanism in game.mechanisms])
            game_models.append(
                f"""
                {game.title}
                ---
                types: {types}
                categories: {categories}
                mechanisms: {mechanisms}
                year: {game.year}
                bgg_rating: {game.bgg_rating}
                complexity: {game.complexity}
                bgg_url: {game.bgg_url}
                image_url: {game.image_url}
                min_players: {game.min_players}
                max_players: {game.max_players}
                min_playtime: {game.min_playtime}
                max_playtime: {game.max_playtime}
                ---
                """
            )
            if fast:
                print(game.title)

    if not game_models:
        augmented_prompt += NO_GAME_FOUND_MSG
        if fast:
            print(NO_GAME_FOUND_MSG)
            sys.exit()
    else:
        augmented_prompt += "\n\n".join(game_models)

    if verbose:
        print("Prompt: ", augmented_prompt)

    if not fast:
        summary_chat = Chat()
        summary_chat.append_chat_history("system", augmented_prompt)
        summary_chat.append_chat_history(
            "user",
            "Briefly summarize the games found",
        )
        response_content = summary_chat.execute()
        print(response_content)
