import os
from typing import List

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, OrderBy, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from .db import Database


class Qdrant:
    collection_name = "games"
    limit = 5
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
        collection = self.client.collection_exists(self.collection_name)
        if not collection:
            print("Creating collection")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.encoder.get_sentence_embedding_dimension(),  # Vector size is defined by used model
                    distance=Distance.COSINE,
                ),
            )

    def insert_collection(self, with_expansions: bool = False):
        all_games = self.db.get_games(with_expansions)

        self.client.upsert(
            collection_name=self.collection_name,
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
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="bgg_id",
                        match=models.MatchAny(any=game_ids),
                    )
                ]
            ),
        )

    def client_search(self, query_filter: models.Filter, query_vector: List[float]):
        return self.client.search(
            collection_name=self.collection_name,
            limit=self.limit,
            query_filter=query_filter,
            query_vector=query_vector,
        )

    def client_scroll(self, scroll_filter: models.Filter):
        return self.client.scroll(
            collection_name=self.collection_name,
            limit=self.limit,
            scroll_filter=scroll_filter,
        )
