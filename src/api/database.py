from datetime import datetime
import json
from typing import Any, Dict, List
from sqlite3 import DatabaseError

from mhooge_flask.database import SQLiteDatabase
from mhooge_flask.logging import logger

from api.stage import Stage

def format_value(key, value):
    if key == "extra":
        return json.loads(value)
    elif key in ("created_at", "changed_at", "started_at", "ended_at"):
        return datetime.fromtimestamp(value).strftime("%d/%m/%Y %H:%M")

    return value

def row_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: format_value(key, value) for key, value in zip(fields, row)}

class Database(SQLiteDatabase):
    def __init__(self):
        super().__init__("../resources/database.db", "../resources/schema.sql", True, row_factory)

    def get_questions_for_user(self, user_id: str, pack_id: str = None, include_public: bool = False):
        where_condition = "(qp.created_by = ?"
        params = [user_id]

        if include_public:
            where_condition += " OR public = 1"

        where_condition += ")"

        if pack_id is not None:
           where_condition += " AND qp.pack_id = ?"
           params.append(pack_id)

        query = f"""
            SELECT
                qp.id AS pack_id,
                qp.name,
                qp.public,
                qp.created_at,
                qp.changed_at,
                qc.id AS category_id,
                qc.name AS category,
                qc.order,
                qt.value,
                qs.id AS question_id,
                qs.round,
                qs.question,
                qs.answer,
                qs.extra
            FROM question_packs AS qp
            INNER JOIN question_tiers AS qt
                ON qp.id = qt.pack_id
            INNER JOIN question_categories AS qc
                ON qt.pack_id = qc.pack_id
            LEFT JOIN questions AS qs
                ON qc.pack_id = qs.pack_id
            WHERE
                {where_condition}
            ORDER BY
                qp.id,
                qs.round,
                qc.order,
                qt.value
        """
        static_ids = ["id", "name", "public", "created_at", "changed_at"]
        question_ids = ["question_id", "value", "question", "answer"]

        with self:
            all_questions = []
            curr_pack = {}
            curr_round = {}
            curr_category = {}
            curr_pack_id = None
            curr_round_num = None
            curr_order = None
            for row in self.execute_query(query, *params):
                if curr_pack_id is not None and curr_pack_id != row["pack_id"]:
                    all_questions.append(curr_pack)

                if curr_pack_id is None or curr_pack_id != row["pack_id"]:
                    curr_pack = {key: row[key] for key in static_ids}
                    curr_pack["rounds"] = []
                    curr_round = {"categories": []}

                if curr_round_num is not None and curr_round_num != row["round"]:
                    curr_pack["rounds"].append(curr_round)
                    curr_round = {"categories": []}
                    curr_category = {"name": row["category"], "order": row["order"], "tiers": []}

                if curr_order is not None and curr_order != row["order"]:
                    curr_round["categories"].append(curr_category)
                    curr_category = {"name": row["category"], "order": row["order"], "tiers": []}

                question_data = {key: row[key] for key in question_ids}
                question_data.update(row["extra"])
                curr_category["tiers"].append(question_data)

                curr_pack_id = row["pack_id"]
                curr_round_num = row["round"]
                curr_order = row["order"]

            return all_questions if pack_id is None else all_questions[0]

    def get_games_for_user(self, user_id: str):
        query = """
            SELECT
                g.id,
                g.title AS game_title,
                qp.name AS pack_name,
                g.regular_rounds,
                g.started_at,
                g.ended_at,
                g.round,
                g.question,
                g.category,
                g.tier,
                g.use_powerups,
                g.stage,
                COUNT(*) AS num_contestants
            FROM games AS g
            INNER JOIN question_packs AS qp
                ON g.pack_id = qp.id
            INNER JOIN contestants AS c
                ON g.id = c.game_id
            GROUP BY game_id
            WHERE g.created_by = ?
        """

        with self:
            return self.execute_query(query, user_id).fetchall()

    def get_contestants_for_game(self, game_id: str):
        query = """
            SELECT
                id,
                name,
                avatar,
                color,
                score,
                buzzes,
                hits,
                misses,
                finale_wager,
                finale_answer
            FROM contestants
            WHERE game_id = ?
        """

        with self:
            return self.execute_query(query, game_id).fetchall()

    def create_question_pack(self, pack_id: str, user_id: str, name: str, public: bool):
        query = """
            INSERT INTO question_packs (id, name, public, created_by, created_at, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        timestamp = datetime.now().timestamp()

        with self:
            self.execute_query(query, pack_id, name, public, user_id, timestamp, timestamp)

    def update_question_pack(
        self,
        pack_id: str,
        title: str,
        public: bool,
        questions: List[Dict[str, Any]]
    ):
        query_pack = """
            UPDATE question_packs
            SET
                name = ?,
                public = ?,
                changed_at = ?
            WHERE id = ?
        """

        query_categories = """
            UPDATE question_categories
            WHERE id = ?
        """

        query_tiers = """
            UPDATE question_tiers
            WHERE id = ?
        """

        query_questions = """
            UPDATE questions
            SET
                category 
            WHERE id = ?
        """

        with self:
            self.execute_query(query_pack, title, public, datetime.now().timestamp(), pack_id, commit=False)

            params = []
            for question_data in questions:
                pass

            self.execute_query()

    def create_game(self, game_id: str, pack_id: str, user_id: str, rounds: int, contestants: int, title: str = None)
        query_game = """
            INSERT INTO games (id, pack_id, title, regular_rounds, created_by, started_at, max_contestants)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        query_questions = f"""
            INSERT INTO game_questions (pack_id, game_id, category, tier, round)
            SELECT q.pack_id, {game_id} AS game_id, p.category, p.tier, p.round
            FROM questions
        """

        try:
            with self:
                self.execute_query(query_game, game_id, pack_id, title, rounds, user_id, datetime.now().timestamp(), contestants)
                self.execute_query(query_questions)

            return True
        except DatabaseError:
            logger.bind(
                game_id=game_id,
                pack_id=pack_id,
                user_id=user_id,
                rounds=rounds,
                contestants=contestants,
                title=title
            ).exception("Database error when creating game")
            return False

    def update_game_state(
        self,
        game_id: str,
        pack_id: str,
        round: int,
        question: int,
        stage: Stage,
        category: str | None = None,
        tier: int | None = None,
    ):
        query_game = "UPDATE games SET round = ?, question = ?, stage = ?"
        query_used = """
            UPDATE game_questions
            SET used = 1
            WHERE
                game_id = ?
                AND pack_id = ?
                AND category = ?
                AND tier = ?
                AND round = ?
        """

        params = [round, question, stage.value]

        if category is not None:
            query_game += ", category = ?"
            params.append(category)
        if tier is not None:
            query_game += ", tier = ?"
            params.append(tier)

        if stage is Stage.ENDED:
            query_game += ", ended_at = ?"
            params.append(datetime.now().timestamp())

        query_game += " WHERE id = ?"
        params.append(game_id)

        with self:
            if category is not None and tier is not None:
                self.execute_query(query_used, game_id, pack_id, category, tier, round, commit=False)

            self.execute_query(query_game, *params)
