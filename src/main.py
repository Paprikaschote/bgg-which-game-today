import os
import sys
from typing import Dict

import requests
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from .bgg import BGG
from .chat import run as run_chat
from .db import Database
from .qdrant import Qdrant

NO_GAME_FOUND_MSG = "No suitable game models were found based on your request."


def setup(
    db: Database,
    client: QdrantClient,
    model: SentenceTransformer,
    bgg_username: str,
    with_expansions: bool = False,
    refresh_data: bool = False,
    verbose: bool = False,
):
    if verbose:
        print("Create tables")
    db.create_tables()
    game_ids = db.get_game_ids()

    if verbose:
        print("Get data from bgg collection")
    bgg = BGG(bgg_username, verbose)
    if refresh_data and verbose:
        print("Refresh data from bgg collection")
    else:
        bgg.set_db_bgg_ids(game_ids)
    bgg.get_data_from_collection()

    if verbose:
        print("insert data into database")
    db.insert_data(bgg.games)

    qdrant = Qdrant(client, db, model, verbose)
    if verbose:
        print("Create Qdrant collection")
    qdrant.create_collection()
    if verbose:
        print("Insert data into Qdrant collection")
    qdrant.insert_collection(with_expansions)
    if verbose:
        print("Delete old entries from the Qdrant collection")
    qdrant.delete_old_entries(game_ids)


def run(config: Dict):
    verbose, fast, refresh_data, expansions = (
        config.get(key) for key in ["verbose", "fast", "refresh", "expansions"]
    )
    encoder = os.environ.get("SENTENCE_TRANFORMER_MODEL", "all-MiniLM-L6-v2")

    if verbose:
        print("Initializing database")
    db = Database()
    if verbose:
        print("Initializing QdrantClient")
    try:
        response = requests.get("http://localhost:6333")
        response.raise_for_status()
        client = QdrantClient(host="localhost", port=6333)
    except requests.RequestException as e:
        raise ConnectionError(f"Docker Container Qdrant is not running: {e}")
    if verbose:
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

                setup(
                    db, client, model, bgg_username, expansions, refresh_data, verbose
                )
            case "chat":
                run_chat(db, client, model, expansions, fast, verbose)
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
