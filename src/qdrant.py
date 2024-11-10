import os
from typing import List

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from .db import Database


class Qdrant:
    encoder_name = os.environ.get("SENTENCE_TRANFORMER_MODEL", "all-MiniLM-L6-v2")
    encoder = SentenceTransformer(encoder_name)

    def __init__(
        self,
        client: QdrantClient,
        db: Database,
        model: SentenceTransformer,
        verbose: bool = False,
    ):
        self.client = client
        self.db = db
        self.model = model
        self.game_ids = []
        self.verbose = verbose

    def create_collection(self):
        collection = self.client.collection_exists("games")
        if not collection:
            print("Creating collection")

            self.client.create_collection(
                collection_name="games",
                vectors_config=VectorParams(
                    size=self.encoder.get_sentence_embedding_dimension(),  # Vector size is defined by used model
                    distance=Distance.COSINE,
                ),
            )

    def insert_collection(self, with_expansions: bool = False):
        all_games = self.db.get_games(with_expansions)

        self.client.upsert(
            collection_name="games",
            points=[
                PointStruct(
                    id=game.bgg_id,
                    vector=self.encoder.encode(game.data_for_vectorization).tolist(),
                    payload=game.to_dict(),
                )
                for game in all_games
            ],
        )

    def delete_old_entries(self, game_ids: List[int]):
        self.client.delete(
            collection_name="games",
            points_selector=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="bgg_id",
                        match=models.MatchAny(any=game_ids),
                    )
                ]
            ),
        )
