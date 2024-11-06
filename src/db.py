#!/usr/bin/env python3

import sqlite3
from typing import List

from .models import Category, Game, Mechanism, Type


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("game-library.db")
        self.conn.row_factory = sqlite3.Row
        self.db_cursor = self.conn.cursor()

    def create_tables(self):
        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS type (
                bgg_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                bgg_url TEXT NOT NULL,
                description TEXT
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS category (
                bgg_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                bgg_url TEXT NOT NULL,
                description TEXT
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS mechanism (
                bgg_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                bgg_url TEXT NOT NULL,
                description TEXT
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS game (
                bgg_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                year INTEGER,
                bgg_rating REAL,
                complexity REAL,
                bgg_url TEXT,
                image_url TEXT,
                expansion BOOLEAN DEFAULT FALSE,
                min_players INTEGER,
                max_players INTEGER,
                min_playtime INTEGER,
                max_playtime INTEGER
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS game_type (
                game_id INTEGER,
                type_id INTEGER,
                FOREIGN KEY (game_id) REFERENCES game(bgg_id),
                FOREIGN KEY (type_id) REFERENCES type(bgg_id),
                PRIMARY KEY (game_id, type_id)
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS game_category (
                game_id INTEGER,
                category_id INTEGER,
                FOREIGN KEY (game_id) REFERENCES game(bgg_id),
                FOREIGN KEY (category_id) REFERENCES category(bgg_id),
                PRIMARY KEY (game_id, category_id)
            )"""
        )

        self.db_cursor.execute(
            """CREATE TABLE IF NOT EXISTS game_mechanism (
                game_id INTEGER,
                mechanism_id INTEGER,
                FOREIGN KEY (game_id) REFERENCES game(bgg_id),
                FOREIGN KEY (mechanism_id) REFERENCES mechanism(bgg_id),
                PRIMARY KEY (game_id, mechanism_id)
            )"""
        )

    def insert_data(self, games: List[Game]):
        for game in games:
            self._insert_game(game)
            self._insert_classifications(game.types, "type", "game_type", game.bgg_id)
            self._insert_classifications(
                game.categories, "category", "game_category", game.bgg_id
            )
            self._insert_classifications(
                game.mechanisms, "mechanism", "game_mechanism", game.bgg_id
            )
            self.conn.commit()

    def _insert_game(self, game: Game):
        self.db_cursor.execute("SELECT * FROM game WHERE bgg_id = ?", (game.bgg_id,))
        if self.db_cursor.fetchone():
            self.db_cursor.execute(
                "UPDATE game SET title = ?, description = ?, year = ?, bgg_rating = ?, complexity = ?, bgg_url = ?, image_url = ?, expansion = ?, min_players = ?, max_players = ?, min_playtime = ?, max_playtime = ? WHERE bgg_id = ?",
                (
                    game.title,
                    game.description,
                    game.year,
                    game.bgg_rating,
                    game.complexity,
                    game.bgg_url,
                    game.image_url,
                    game.expansion,
                    game.min_players,
                    game.max_players,
                    game.min_playtime,
                    game.max_playtime,
                    game.bgg_id,
                ),
            )
        else:
            self.db_cursor.execute(
                "INSERT INTO game (bgg_id, title, description, year, bgg_rating, complexity, bgg_url, image_url, expansion, min_players, max_players, min_playtime, max_playtime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game.bgg_id,
                    game.title,
                    game.description,
                    game.year,
                    game.bgg_rating,
                    game.complexity,
                    game.bgg_url,
                    game.image_url,
                    game.expansion,
                    game.min_players,
                    game.max_players,
                    game.min_playtime,
                    game.max_playtime,
                ),
            )

    def _insert_classifications(
        self, classifications, table_name, link_table_name, game_id
    ):

        for classification in classifications:
            # classification insert/update
            self.db_cursor.execute(
                f"SELECT * FROM {table_name} WHERE bgg_id = ?", (classification.bgg_id,)
            )
            if not self.db_cursor.fetchone():
                self.db_cursor.execute(
                    f"INSERT INTO {table_name} (bgg_id, name, bgg_url, description) VALUES (?, ?, ?, ?)",
                    (
                        classification.bgg_id,
                        classification.name,
                        classification.bgg_url,
                        classification.description,
                    ),
                )
            else:
                self.db_cursor.execute(
                    f"UPDATE {table_name} SET name = ?, bgg_url = ?, description = ? WHERE bgg_id = ?",
                    (
                        classification.name,
                        classification.bgg_url,
                        classification.description,
                        classification.bgg_id,
                    ),
                )

            # Many-To-Many relationship between games and classifications
            self.db_cursor.execute(
                f"SELECT * FROM {link_table_name} WHERE game_id = ? AND {table_name}_id = ?",
                (game_id, classification.bgg_id),
            )
            if not self.db_cursor.fetchone():
                self.db_cursor.execute(
                    f"INSERT INTO {link_table_name} (game_id, {table_name}_id) VALUES (?, ?)",
                    (game_id, classification.bgg_id),
                )

    def get_classification_by_id(self, bgg_id: int, classification: str):
        self.db_cursor.execute(
            f"SELECT * FROM {classification} WHERE bgg_id = {bgg_id}",
        )
        return self.db_cursor.fetchone()

    def get_type_names(self, bgg_id: int):
        self.db_cursor.execute(
            f"SELECT name FROM type WHERE bgg_id IN (SELECT type_id FROM game_type WHERE bgg_id = {bgg_id})"
        )
        return self.db_cursor.fetchall()

    def get_category_names(self, bgg_id: int):
        self.db_cursor.execute(
            f"SELECT name FROM category WHERE bgg_id IN (SELECT category_id FROM game_category WHERE bgg_id = {bgg_id})"
        )
        return self.db_cursor.fetchall()

    def get_mechanism_names(self, bgg_id: int):
        self.db_cursor.execute(
            f"SELECT name FROM mechanism WHERE bgg_id IN (SELECT mechanism_id FROM game_mechanism WHERE bgg_id = {bgg_id})"
        )
        return self.db_cursor.fetchall()

    def get_games(self, with_expansions: bool = False) -> List[Game]:
        with_expansions = int(with_expansions)
        query = f"""
            SELECT g.bgg_id, g.title, g.description, g.year, g.bgg_rating, g.complexity,
                g.bgg_url, g.image_url, g.min_players, g.max_players, g.min_playtime, g.max_playtime,
                (SELECT GROUP_CONCAT(DISTINCT c.bgg_id || ':' || c.name)
                    FROM category c
                    JOIN game_category gc ON gc.category_id = c.bgg_id
                    WHERE gc.game_id = g.bgg_id) AS categories,
                (SELECT GROUP_CONCAT(DISTINCT t.bgg_id || ':' || t.name)
                    FROM type t
                    JOIN game_type gt ON gt.type_id = t.bgg_id
                    WHERE gt.game_id = g.bgg_id) AS types,
                (SELECT GROUP_CONCAT(DISTINCT m.bgg_id || ':' || m.name)
                    FROM mechanism m
                    JOIN game_mechanism gm ON gm.mechanism_id = m.bgg_id
                    WHERE gm.game_id = g.bgg_id) AS mechanisms
            FROM game g
            WHERE g.expansion = {with_expansions}
            GROUP BY g.bgg_id
        """

        self.db_cursor.execute(query)
        rows = self.db_cursor.fetchall()

        games = []
        for row in rows:
            categories, types, mechanisms = [], [], []
            if row["categories"]:
                categories = [
                    Category(int(cat.split(":")[0]), cat.split(":")[1])
                    for cat in row["categories"].split(",")
                ]
            if row["types"]:
                types = [
                    Type(int(typ.split(":")[0]), typ.split(":")[1])
                    for typ in row["types"].split(",")
                ]
            if row["mechanisms"]:
                mechanisms = [
                    Mechanism(int(mech.split(":")[0]), mech.split(":")[1])
                    for mech in row["mechanisms"].split(",")
                ]
            game = Game(
                bgg_id=row[0],
                title=row[1],
                description=row[2],
                year=row[3],
                bgg_rating=row[4],
                complexity=row[5],
                bgg_url=row[6],
                image_url=row[7],
                min_players=row[8],
                max_players=row[9],
                min_playtime=row[10],
                max_playtime=row[11],
                categories=categories,
                types=types,
                mechanisms=mechanisms,
            )
            games.append(game)

        return games

    def close(self):
        self.conn.close()
