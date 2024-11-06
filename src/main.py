#!/usr/bin/env python3

import json
import os
import sys
from typing import Dict, Literal, Union

import requests
from openai import OpenAI
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from .bgg import BGG
from .db import Database
from .qdrant import Qdrant

NO_GAME_FOUND_MSG = "No suitable game models were found based on your request."


class Chat:
    use_openai = os.environ.get("USE_OPENAI", False) == "True"
    gpt_chat_model = os.environ.get("GPT_CHAT_MODEL", "gpt-4o-mini")
    local_chat_model = os.environ.get("LOCAL_CHAT_MODEL", "llama-3.2-3b-instruct:q8_0")

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
        self, client: QdrantClient, model: SentenceTransformer, verbose: bool = False
    ):
        super().__init__(verbose)
        self.client = client
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
        print("START")
        search_result = self.client.search(
            collection_name="games",
            limit=3,
            query_filter=models.Filter(
                # must=self.filter_players_playtime,
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
            query_vector=self.model.encode(self.json_content["description"]).tolist(),
        )

        # search_result = self.client.search(
        #     collection_name="games",
        #     limit=3,
        #     query_filter=models.Filter(
        #         must=self.filter_players_playtime,
        #         should=self.filter_categories,
        #     ),
        #     query_vector=self.model.encode(self.json_content["description"]).tolist(),
        # )
        print("!")
        print(search_result)
        exit(1)
        if not search_result:
            search_result = self.client.search(
                collection_name="games",
                limit=3,
                query_filter=models.Filter(
                    must=self.filter_players_playtime,
                    should=[
                        models.Filter(should=self.filter_complexity),
                        models.Filter(should=self.filter_categories),
                    ],
                ),
                query_vector=self.model.encode(
                    self.json_content["description"]
                ).tolist(),
            )

            if not search_result:
                search_result = self.client.search(
                    collection_name="games",
                    limit=3,
                    query_filter=models.Filter(must=self.filter_players_playtime),
                    query_vector=self.model.encode(
                        self.json_content["description"]
                    ).tolist(),
                )
        if self.verbose:
            print(search_result)
        return search_result


def run_chat(
    db: Database,
    client: QdrantClient,
    model: SentenceTransformer,
    chat_model: str,
    with_expansions: bool = False,
    fast: bool = False,
    verbose: bool = False,
):
    all_games_dict = {game.bgg_id: game for game in db.get_games(with_expansions)}

    prepare_chat = PrepareChat(client, model, verbose)
    prepare_chat.check()

    prepare_prompt = """Your sole responsibility is to analyze the user's prompt and extract relevant information to enhance board game search capabilities. Respond exclusively with a JSON object following the schema below, filling in the values based on the user's statement. Do not include any additional text or explanations. For any information that cannot be assigned to a specific value in the JSON, include it in the 'description' key. If no relevant data is available, remove the key from the json. At the end no None values should be present in the JSON object.

    The values for players, playtime, and complexity must be provided as integers. The playtime must be converted to minutes. The complexity should range from 0 to 5, based on the weight value from boardgamegeeks.com. The language of the user's request must be included in the 'language' key and should be written as an English word. The genre must be a list of values, and the description should be a flowing text provided in English, regardless of the user's language.

    === SCHEMA
    {
        "min_players": None,
        "max_players": None,
        "min_playtime": None,
        "max_playtime": None,
        "complexity": None,
        "description": None,
        "genre": None,
        "language": None,
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
        print("Prepare Search", response_content)

    prepare_chat.read_filter(response_content)
    search_result = prepare_chat.search_result()

    language = prepare_chat.get_language()

    augmented_prompt = f"""You are a board game recommendation assistant. Summarize every single entry of games from the game recommendations below in a maximum of two sentences each. If no game recommendations are found, apologize and state that no suitable game is available. Answer in {language}.

    === GAME RECOMMANDATIONS

    """

    game_models = []
    for r in search_result:
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
            exit(1)
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


def setup(
    db: Database,
    client: QdrantClient,
    model: SentenceTransformer,
    bgg_username: str,
    with_expansions: bool = False,
    skip: bool = False,
    verbose: bool = False,
):
    print("Create tables")
    db.create_tables()

    print("Get data from bgg collection")
    bgg = BGG(bgg_username, verbose)
    bgg.get_data_from_collection()

    print("insert data into database")
    db.insert_data(bgg.games)

    qdrant = Qdrant(client, db, model, verbose)
    print("Create QdrantCollection")
    qdrant.create_collection()
    print("Insert data into QdrantCollection")
    qdrant.insert_collection(with_expansions)
    qdrant.delete_old_entries(bgg.games)


def run(config: Dict):
    verbose, fast, skip, expansions = (
        config.get(key) for key in ["verbose", "fast", "skip", "expansions"]
    )
    encoder = os.environ.get("SENTENCE_TRANFORMER_MODEL", "all-MiniLM-L6-v2")

    print("Initializing database")
    db = Database()
    print("Initializing QdrantClient")
    try:
        response = requests.get("http://localhost:6333")
        response.raise_for_status()
        client = QdrantClient(host="localhost", port=6333)
    except requests.RequestException as e:
        raise ConnectionError(f"Docker Container Qdrant is not running: {e}")
    print("Initializing SentenceTransformerModel")
    model = SentenceTransformer(
        encoder,
        tokenizer_kwargs={
            "clean_up_tokenization_spaces": False,
        },
    )

    try:
        match config["mode"]:
            case "db":
                bgg_username = os.environ.get("BGG_USERNAME")
                if not bgg_username:
                    raise EnvironmentError("No BGG_USERNAME environment variable found")

                setup(db, client, model, bgg_username, expansions, skip, verbose)
            case "chat":
                chat_model = os.environ.get(
                    "LOCAL_CHAT_MODEL", "llama-3.2-3b-instruct:q8_0"
                )
                run_chat(db, client, model, chat_model, expansions, fast, verbose)
            case _:
                print("Invalid mode")
                sys.exit(1)
    except EnvironmentError as e:
        print(f"Environment error: {e}")
        sys.exit(1)
    except ConnectionError as e:
        print(f"Connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        db.close()
