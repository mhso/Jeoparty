from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, DateTime, Enum, JSON, ForeignKey, case
from sqlalchemy.orm import mapped_column, Mapped, relationship

from mhooge_flask.database import Base

from jeoparty.api.enums import StageType, PowerUpType, Language
from jeoparty.api.config import (
    Config, 
    get_avatar_path,
    get_bg_image_path,
    get_buzz_sound_path,
    get_data_path_for_question_pack
)

power_up_order_case = {power_up.name: index for index, power_up in enumerate(PowerUpType)}

class PowerUp(Base):
    __tablename__ = "power_ups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    type: Mapped[PowerUpType] = mapped_column(Enum(PowerUpType))
    icon: Mapped[Optional[str]] = mapped_column(String(128))
    video: Mapped[Optional[str]] = mapped_column(String(128))

    game_power_ups = relationship("GamePowerUp", back_populates="power_up", cascade="all, delete-orphan", order_by="GamePowerUp.id.asc()")
    pack = relationship("QuestionPack", back_populates="power_ups")

    @property
    def extra_fields(self):
        return {
            "icon": f"img/{self.type.value}_power.png" if not self.icon else f"{get_data_path_for_question_pack(self.pack_id, False)}/{self.icon}",
            "video": f"img/{self.type.value}_power_used.webm" if not self.icon else f"{get_data_path_for_question_pack(self.pack_id, False)}/{self.video}",
        }

class QuestionPack(Base):
    __tablename__ = "question_packs"
    __validate_fields__ = {
        "name": {"min_length": 3, "pattern": Config.VALID_NAME_CHARACTERS},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    include_finale: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.ENGLISH)
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    creator = relationship("User")
    rounds = relationship("QuestionRound", back_populates="pack", cascade="all, delete-orphan", order_by="QuestionRound.round.asc()")
    games = relationship("Game", back_populates="pack", cascade="all, delete-orphan", order_by="Game.started_at.asc()")
    buzzer_sounds = relationship("BuzzerSound", back_populates="pack", cascade="all, delete-orphan", order_by="BuzzerSound.id.asc()")
    power_ups = relationship("PowerUp", back_populates="pack", cascade="all, delete-orphan", order_by="PowerUp.pack_id.asc()")

    def get_all_questions(self):
        questions = []
        for round_data in self.rounds:
            for category_data in round_data.categories:
                for question_data in category_data.questions:
                    questions.append(question_data)

        return questions

class QuestionRound(Base):
    __tablename__ = "question_rounds"
    __validate_fields__ = {
        "name": {"min_length": 1, "pattern": Config.VALID_NAME_CHARACTERS},
        "round": {"gt": 0, "le": 10},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    name: Mapped[str] = mapped_column(String(64))
    round: Mapped[int] = mapped_column(Integer)

    pack = relationship("QuestionPack", back_populates="rounds")
    categories = relationship("QuestionCategory", back_populates="round", cascade="all, delete-orphan", order_by="QuestionCategory.order.asc()")

    def dump_questions_nested(self, remap_keys: bool = True, **keys_to_delete):
        def get_key_map(key: str):
            if not remap_keys:
                return {}

            return {"id": f"{key}_id"}

        round_json = self.dump(**get_key_map("round"))
        round_json["categories"] = []

        for key in keys_to_delete.get("round", []):
            del round_json[key]

        for category in self.categories:
            category_json = category.dump(**get_key_map("category"))
            category_json["questions"] = []

            for key in keys_to_delete.get("category", []):
                del category_json[key]

            for question in category.questions:
                question_json = question.dump(**get_key_map("question"))

                for key in keys_to_delete.get("question", []):
                    del question_json[key]

                category_json["questions"].append(question_json)

            round_json["categories"].append(category_json)

        return round_json

class QuestionCategory(Base):
    __tablename__ = "question_categories"
    __validate_fields__ = {
        "name": {"min_length": 1, "pattern": Config.VALID_NAME_CHARACTERS},
        "buzz_time": {"ge": 0, "le": 60},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    round_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_rounds.id"))
    name: Mapped[str] = mapped_column(String(64))
    order: Mapped[int] = mapped_column(Integer)
    buzz_time: Mapped[Optional[int]] = mapped_column(Integer, default=10)
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    round = relationship("QuestionRound", back_populates="categories")
    questions = relationship("Question", back_populates="category", cascade="all, delete-orphan", order_by="Question.value.asc()")

    @property
    def extra_fields(self):
        return {
            "bg_image": None if not self.bg_image else f"{get_bg_image_path(False)}/{self.bg_image}",
        }

class Question(Base):
    __tablename__ = "questions"
    __validate_fields__ = {
        "question": {"min_length": 3, "max_length": 128, "pattern": Config.VALID_NAME_CHARACTERS},
        "answer": {"min_length": 1, "max_length": 128, "pattern": Config.VALID_NAME_CHARACTERS},
        "value": {"gt": 0, "lt": 10000},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    category_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_categories.id"))
    question: Mapped[str] = mapped_column(String(128))
    answer: Mapped[str] = mapped_column(String(128))
    value: Mapped[int] = mapped_column(Integer)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    category = relationship("QuestionCategory", back_populates="questions")
    game_questions = relationship("GameQuestion", back_populates="question", cascade="all, delete-orphan", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")

    @property
    def extra_fields(self):
        if self.extra is None:
            return {}
        
        fields = dict(self.extra)

        for key in ("question_image", "video", "answer_image"):
            if key in self.extra:
                fields[key] = f"{get_data_path_for_question_pack(self.category.round.pack_id, False)}/{self.extra[key]}"

        return {"extra": fields}

class BuzzerSound(Base):
    __tablename__ = "buzzer_sounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(128))
    correct: Mapped[bool] = mapped_column(Boolean)

    pack = relationship("QuestionPack", back_populates="buzzer_sounds")

class Contestant(Base):
    __tablename__ = "contestants"
    __validate_fields__ = {
        "name": {"min_length": 2, "max_length": 16, "pattern": Config.VALID_NAME_CHARACTERS},
        "color": {"min_length": 1, "max_length": 16},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(16))
    color: Mapped[str] = mapped_column(String(16))
    avatar: Mapped[Optional[str]] = mapped_column(String(128))
    buzz_sound: Mapped[Optional[str]] = mapped_column(String(128))
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    game_contestants = relationship("GameContestant", back_populates="contestant", cascade="all, delete-orphan", order_by="GameContestant.game_id.asc(), GameContestant.contestant_id.asc()")

    @property
    def extra_fields(self):
        avatar = self.avatar if self.avatar else Config.DEFAULT_AVATAR
        return {
            "avatar": f"{get_avatar_path(False)}/{avatar}",
            "buzz_sound": None if not self.buzz_sound else f"{get_buzz_sound_path(False)}/{self.buzz_sound}",
            "bg_image": None if not self.bg_image else f"{get_bg_image_path(False)}/{self.bg_image}",
        }

class GamePowerUp(Base):
    __tablename__ = "game_power_ups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"))
    contestant_id: Mapped[str] = mapped_column(String(64), ForeignKey("game_contestants.id"))
    power_id: Mapped[str] = mapped_column(String(128), ForeignKey("power_ups.id"))
    type: Mapped[PowerUpType] = mapped_column(Enum(PowerUpType))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    power_up = relationship("PowerUp", back_populates="game_power_ups")
    contestant = relationship("GameContestant", back_populates="power_ups")

    @property
    def extra_fields(self):
        return self.power_up.extra_fields

class GameContestant(Base):
    __tablename__ = "game_contestants"
    __validate_fields__ = {
        "score": {"ge": 0},
        "buzzes": {"ge": 0},
        "hits": {"ge": 0},
        "misses": {"ge": 0},
        "finale_wager": {"ge": 0},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"), primary_key=True)
    contestant_id: Mapped[str] = mapped_column(String(64), ForeignKey("contestants.id"), primary_key=True)
    has_turn: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    buzzes: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    misses: Mapped[int] = mapped_column(Integer, default=0)
    finale_wager: Mapped[Optional[int]] = mapped_column(Integer)
    finale_answer: Mapped[Optional[str]] = mapped_column(String(128))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    game = relationship("Game", back_populates="game_contestants")
    contestant = relationship("Contestant", back_populates="game_contestants")
    power_ups = relationship("GamePowerUp", back_populates="contestant", cascade="all, delete-orphan", order_by=case(power_up_order_case, value=GamePowerUp.type))

    @property
    def extra_fields(self):
        return {
            "name": self.contestant.name,
            "color": self.contestant.color,
            **self.contestant.extra_fields
        }

    def get_power(self, power: PowerUpType) -> GamePowerUp | None:
        for power_up in self.power_ups:
            if power_up.type is power:
                return power_up

        return None

class GameQuestion(Base):
    __tablename__ = "game_questions"

    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("questions.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_double: Mapped[bool] = mapped_column(Boolean, default=False)

    game = relationship("Game", back_populates="game_questions")
    question = relationship("Question", back_populates="game_questions")

class Game(Base):
    __tablename__ = "games"
    __validate_fields__ = {
        "title": {"min_length": 3, "pattern": Config.VALID_NAME_CHARACTERS},
        "password": {"min_length": 3, "max_length": 128},
        "regular_rounds": {"gt": 0, "lt": 10},
        "max_contestants": {"gt": 0, "lt": 10},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    title: Mapped[str] = mapped_column(String(32))
    join_code: Mapped[str] = mapped_column(String(64))
    regular_rounds: Mapped[int] = mapped_column(Integer, default=Config.REGULAR_ROUNDS)
    max_contestants: Mapped[int] = mapped_column(Integer)
    use_daily_doubles: Mapped[bool] = mapped_column(Boolean, default=True)
    use_powerups: Mapped[bool] = mapped_column(Boolean, default=True)
    stage: Mapped[StageType] = mapped_column(Enum(StageType), default=StageType.LOBBY)
    round: Mapped[int] = mapped_column(Integer, default=1)
    password: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    pack = relationship("QuestionPack", back_populates="games")
    game_questions = relationship("GameQuestion", back_populates="game", cascade="all, delete-orphan", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")
    game_contestants = relationship("GameContestant", back_populates="game", cascade="all, delete-orphan", order_by="GameContestant.joined_at.asc()")

    @property
    def extra_fields(self):
        player_with_turn = self.get_contestant_with_turn()
        questions_for_round = self.get_questions_for_round()

        return {
            "total_rounds": self.regular_rounds + 1 if self.pack and self.pack.include_finale else self.regular_rounds,
            "player_with_turn": player_with_turn.dump(include_relations=False) if player_with_turn else None,
            "max_value": max(gq.question.value for gq in questions_for_round) if questions_for_round else 0,
            "question_num": sum(1 if gq.used else 0 for gq in self.game_questions) + 1,
        }

    def get_contestant(self, contestant_id: str | None) -> Contestant | None:
        if contestant_id is None:
            return None

        for contestant in self.game_contestants:
            if contestant.contestant_id == contestant_id:
                return contestant.contestant

        return None
    
    def get_game_contestant(self, contestant_id: str | None) -> GameContestant | None:
        if contestant_id is None:
            return None

        for contestant in self.game_contestants:
            if contestant.id == contestant_id:
                return contestant

        return None

    def get_question(self, question_id: str) -> GameQuestion | None:
        for question in self.game_questions:
            if question.question_id == question_id:
                return question
            
        return None

    def get_contestant_with_turn(self) -> GameContestant | None:
        for contestant in self.game_contestants:
            if contestant.has_turn:
                return contestant

        return None

    def get_questions_for_round(self) -> List[GameQuestion]:
        return [
            game_question for game_question in self.game_questions
            if game_question.question.category.round.round == self.round
        ]

    def get_active_question(self) -> GameQuestion | None:
        for question in self.game_questions:
            if question.active:
                return question

        return None

    def get_game_winners(self):
        sorted_contestants = sorted(
            self.game_contestants,
            key=lambda x: x.score,
            reverse=True
        )

        ties = 0
        for index, contessant in enumerate(sorted_contestants[1:], start=1):
            if sorted_contestants[index-1].score > contessant.score:
                break

            ties += 1

        return sorted_contestants[:ties + 1]

    def set_contestant_turn(self, contestant_id: str):
        for contestant in self.game_contestants:
            contestant.has_turn = contestant.contestant_id == contestant_id
