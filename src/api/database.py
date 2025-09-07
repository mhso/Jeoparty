from datetime import datetime
import json
from typing import List
import traceback

from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload, Session

from mhooge_flask.database import SQLAlchemyDatabase

from api.config import ROUND_NAMES, FINALE_NAME
from api.enums import StageType
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
        super().__init__("../resources/database.db", "api/orm", True)

    def get_questions_for_user(self, user_id: str, pack_id: str = None, include_public: bool = False) -> List[QuestionPack] | QuestionPack:
        with self as session:
            if include_public:
                filters = [(QuestionPack.created_by == user_id) | (QuestionPack.public == True)]
            else:
                filters = [QuestionPack.created_by == user_id]

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

            if data == []:
                return [] if pack_id is None else None

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
                selectinload(Game.game_contestants).selectinload(GameContestant.power_ups).selectinload(GamePowerUp.power_up)
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
                for question in self.get_questions_for_user(game_model.created_by, game_model.pack_id, True).get_all_questions()
            ]
            session.add_all(game_questions)

            session.commit()
            session.refresh(game_model)

    def save_model(self, model: Base):
        with self as session:
            session.add(model)
            session.commit()

            session.refresh(model)

    def save_game(self, game_model: Game):
        if game_model.stage is StageType.ENDED:
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

    def get_model_from_id(self, model: type[Base], data: Dict[str, Any], key_name: str = "id"):
        with self as session:
            key_value = data.get(key_name)
            if key_value is None:
                return None

            stmt = select(model).where(getattr(model, key_name) == key_value)
            try:
                return session.execute(stmt).scalar_one()
            except Exception:
                return None

    def create_or_get_model(self, session: Session, model: type[Base], data: Dict[str, Any], key_name: str = "id"):
        key_value = data.get(key_name)
        if key_value is None:
            return None

        stmt = select(model).where(getattr(model, key_name) == key_value)
        result = session.execute(stmt).first()

        if result is not None:
            return result

        model_instance = model(**data)
        session.add(model_instance)

        return model_instance

    def _get_update_statement(self, old_model: Base, new_model: Base, id_key: str = "id"):
        changed_columns = {}
        for c in old_model.__table__.columns:
            key = c.name
            if key == id_key:
                continue

            old_value = getattr(old_model, key)
            new_value = getattr(new_model, key)

            if old_value != new_value:
                changed_columns[key] = new_value

        if changed_columns == {}:
            return None

        _class = type(old_model)
        return update(_class).where(getattr(_class, id_key) == getattr(old_model, id_key)).values(**changed_columns)

    def update_question_pack(self, data: Dict[str, Any]):
        data_to_delete = []

        with self as session:
            pack_model = session.execute(select(QuestionPack).where(QuestionPack.id == data["id"])).scalar_one()

            # Unpack rounds, categories, and questions into separate models
            round_index = 1
            for round_data in data["rounds"]:
                round_data["pack_id"] = pack_model.id
    
                if round_data.get("deleted", False):
                    data_to_delete.append((QuestionRound, round_data["id"]))
                    continue

                category_models = []
                for category_data in round_data["categories"]:
                    if category_data.get("deleted", False):
                        data_to_delete.append((QuestionCategory, category_data["id"]))
                    else:
                        category_models.append(category_data)

                round_data["round"] = round_index
                del round_data["categories"]
                new_round_model = QuestionRound(**round_data)

                if "id" in round_data:
                    round_model = self.get_model_from_id(QuestionRound, round_data)
                    update_stmt = self._get_update_statement(round_model, new_round_model)

                    if update_stmt is not None:
                        session.execute(update_stmt)
                else:
                    round_model = new_round_model
                    session.add(round_model)
                    session.flush()

                category_index = 0
                for category_data in category_models:
                    category_data["round_id"] = round_model.id

                    question_models = []
                    for question_data in category_data["questions"]:
                        if question_data.get("deleted", False):
                            data_to_delete.append((Question, question_data["id"]))
                        else:
                            question_models.append(question_data)

                    category_data["order"] = category_index
                    del category_data["questions"]
                    new_category_model = QuestionCategory(**category_data)

                    if "id" in category_data:
                        category_model = self.get_model_from_id(QuestionCategory, category_data)
                        update_stmt = self._get_update_statement(category_model, new_category_model)

                        if update_stmt is not None:
                            session.execute(update_stmt)
                    else:
                        category_model = new_category_model
                        session.add(category_model)
                        session.flush()

                    for question_data in question_models:
                        question_data["category_id"] = category_model.id

                        new_question_model = Question(**question_data)

                        if "id" in question_data:
                            question_model = self.get_model_from_id(Question, question_data)
                            update_stmt = self._get_update_statement(question_model, new_question_model)
                            if update_stmt is not None:
                                session.execute(update_stmt)
                        else:
                            question_model = new_question_model
                            session.add(question_model)

                    category_index += 1

                round_index += 1

            # Perform deletes if there are any
            for model, model_id in data_to_delete:
                session.execute(delete(model).where(model.id == model_id))

            session.commit()
