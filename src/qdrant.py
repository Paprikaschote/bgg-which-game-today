import os
from typing import List

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from .db import Database
from .models import Game


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

        self.client.upload_points(
            collection_name="games",
            points=[
                PointStruct(
                    id=game.bgg_id,
                    vector=self.encoder.encode(game.description).tolist(),
                    payload=game.to_dict(show_description=False),
                )
                for game in all_games
            ],
        )

    def delete_old_entries(self, games: List[Game]):

        # self.client.delete(
        #     collection_name="games",
        #     points_selector=models.Filter(
        #         must_not=[
        #             models.FieldCondition(
        #                 key="bgg_id",
        #                 match=models.MatchAny(any=[game.bgg_id for game in games]),
        #             )
        #         ]
        #     ),
        # )

        print(
            models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="bgg_id",
                        match=models.MatchAny(any=[game.bgg_id for game in games]),
                    )
                ]
            )
        )

        # for game in all_games:
        #     # types = ", ".join([game_type.name for game_type in game.types])
        #     # categories = ", ".join([category.name for category in game.categories])
        #     # mechanisms = ", ".join([mechanism.name for mechanism in game.mechanisms])

        #     types = [game_type.name for game_type in game.types]
        #     categories = [category.name for category in game.categories]
        #     mechanisms = [mechanism.name for mechanism in game.mechanisms]

        #     embedded_content = f"""
        #     {{
        #         "type": {types},
        #         "title": "{game.title}",
        #         "categories": {categories},
        #         "mechanisms": {mechanisms},
        #         "min_players": {game.min_players},
        #         "max_players": {game.max_players},
        #         "min_playtime": {game.min_playtime},
        #         "max_playtime": {game.max_playtime}
        #     }}
        #     """

        #     if self.verbose:
        #         print("Insert Collection with content", embedded_content)

        #     embedding = self.model.encode(
        #         embedded_content,
        #         normalize_embeddings=True,
        #         output_value="token_embeddings",
        #     )

        #     self.client.upsert(
        #         collection_name="games",
        #         wait=True,
        #         points=[
        #             {
        #                 "id": game.bgg_id,
        #                 "vector": embedding.data[0],
        #                 "payload": {
        #                     "name": game.title,
        #                     "types": types,
        #                     "categories": categories,
        #                     "mechanisms": mechanisms,
        #                     "year": game.year,
        #                     "bgg_rating": game.bgg_rating,
        #                     "complexity": game.complexity,
        #                     "bgg_url": game.bgg_url,
        #                     "image_url": game.image_url,
        #                     "min_players": game.min_players,
        #                     "max_players": game.max_players,
        #                     "min_playtime": game.min_playtime,
        #                     "max_playtime": game.max_playtime,
        #                     "description": {game.description},
        #                 },
        #             },
        #         ],
        #     )
