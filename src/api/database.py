from datetime import datetime
import json
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mhooge_flask.database import SQLAlchemyDatabase
from mhooge_flask.logging import logger

from api.config import ROUND_NAMES, FINALE_NAME
from api.enums import Stage
from api.orm.base import Base
from api.orm.models import *

def format_value(key, value):
    if key == "extra":
        return json.loads(value)
    elif key in ("created_at", "changed_at", "started_at", "ended_at"):
        return datetime.fromtimestamp(value).strftime("%d/%m/%Y %H:%M")

    return value

def row_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: format_value(key, value) for key, value in zip(fields, row)}

class Database(SQLAlchemyDatabase):
    def __init__(self):
        super().__init__("../resources/database.db", "api/orm", Base, True)

    def get_questions_for_user(self, user_id: str, pack_id: str = None, include_public: bool = False) -> List[QuestionPack] | QuestionPack:
        with self as session:
            filters = [QuestionPack.created_at == user_id or QuestionPack.public == False or QuestionPack.public == include_public]
            if pack_id is not None:
                filters.append(QuestionPack.id == pack_id)

            statement = select(QuestionPack).options(
                selectinload(QuestionPack.rounds).
                selectinload(QuestionRound.categories).
                selectinload(QuestionCategory.questions)
            ).options(
                selectinload(QuestionPack.buzzer_sounds)
            ).filter(*filters)

            data = session.execute(statement).scalars().all()

            return data if pack_id is None else data[0]

    def get_game_from_id(self, game_id: str):
        with self as session:
            statement = select(Game).options(
                selectinload(Game.pack).options(
                    selectinload(QuestionPack.rounds), selectinload(QuestionPack.buzzer_sounds)
                ).selectinload(QuestionRound.categories).selectinload(QuestionCategory.questions)
            ).options(
                selectinload(Game.questions).selectinload(GameQuestion.question)
            ).options(
                selectinload(Game.game_contestants).selectinload(GameContestant.power_ups)
            ).options(
                selectinload(Game.power_ups)
            ).filter(Game.id == game_id)

            return session.execute(statement).scalar_one()

    def get_games_for_user(self, user_id: str):
        with self as session:
            statement = select(Game).options(
                selectinload(Game.pack).selectinload(QuestionPack.rounds).selectinload(QuestionRound.categories).selectinload(QuestionCategory.questions)
            ).options(
                selectinload(Game.questions).selectinload(GameQuestion.question)
            ).options(
                selectinload(Game.game_contestants).selectinload(GameContestant.power_ups)
            ).options(
                selectinload(Game.power_ups)
            ).filter(Game.created_by == user_id)

            return session.execute(statement).scalars().all()

    def get_contestants_for_game(self, game_id: str) -> List[GameContestant]:
        with self as session:
            statement = select(GameContestant).options(
                selectinload(GameContestant.power_ups)
            ).filter(GameContestant.game_id == game_id)

            return session.execute(statement).scalars().all()

    def get_contestant_from_id(self, user_id: str) -> Contestant:
        with self as session:
            statement = select(Contestant).options(
                selectinload(Contestant.game_contestants)
            ).filter(Contestant.id == user_id)

            return session.execute(statement).scalar_one()

    def create_question_pack(self, pack_model: QuestionPack):
        with self as session:
            session.add(pack_model)
            session.flush()

            rounds_to_create = []
            if pack_model.rounds == []:
                rounds_to_create = [(1, ROUND_NAMES[0])]
                if pack_model.include_finale:
                    rounds_to_create.append((2, FINALE_NAME))

            for (round_num, name) in rounds_to_create:
                session.add(QuestionRound(pack_id=pack_model.id, name=name, round=round_num))

            session.commit()
            session.refresh(pack_model)

            return pack_model

    def save_question_pack(self, pack_model: QuestionPack):
        with self as session:
            session.add(pack_model)
            session.commit()

            session.refresh(pack_model)

            return pack_model

    def create_game(self, game_model: Game):
        with self as session:
            session.add(game_model)
            session.flush()

            # Add a fresh batch of game questions
            game_questions = [
                GameQuestion(
                    game_id=game_model.id,
                    question_id=question.id,
                ) 
                for question in self.get_questions_for_user(game_model.created_by, game_model.pack_id, True)
            ]
            session.add_all(game_questions)

            session.commit()
            session.refresh(game_model)

    def save_game(self, game_model: Game):
        if game_model.stage is Stage.ENDED:
            game_model.ended_at = datetime.now()

        with self as session:
            session.add(game_model)

            session.commit()
            session.refresh(game_model)

    def save_game_question(self, game_question_model: GameQuestion):
        with self as session:
            session.add(game_question_model)

            session.commit()
            session.refresh(game_question_model)

    def save_contenstant(self, contestant_model: Contestant):
        with self as session:
            session.add(contestant_model)

            session.commit()
            session.refresh(contestant_model)

    def add_contestant_to_game(self, game_contestant_model: GameContestant):
        with self as session:
            session.add(game_contestant_model)

            session.commit()
            session.refresh(game_contestant_model)
