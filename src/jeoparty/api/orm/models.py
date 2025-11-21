from datetime import datetime
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, Boolean, DateTime, Enum, JSON, ForeignKey, case
from sqlalchemy.orm import mapped_column, Mapped, relationship

from mhooge_flask.database import Base

from jeoparty.api.enums import StageType, PowerUpType, Language
from jeoparty.api.config import (
    Config, 
    get_theme_path,
    get_question_pack_data_path,
    get_buzz_sound_path,
)

power_up_order_case = {power_up.name: index for index, power_up in enumerate(PowerUpType)}

class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.ENGLISH)
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    creator = relationship("User")
    packs = relationship("QuestionPack", back_populates="theme", order_by="QuestionPack.name.asc()")
    buzzer_sounds = relationship("BuzzerSound", back_populates="theme", cascade="all, delete", order_by="BuzzerSound.id.asc()")

    __serialize_relationships__ = [creator, buzzer_sounds]

class QuestionPack(Base):
    __tablename__ = "question_packs"
    __validate_fields__ = {
        "name": {"min_length": 3, "pattern": Config.VALID_TITLE_CHARACTERS},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    include_finale: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.ENGLISH)
    theme_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("themes.id"))
    lobby_music: Mapped[Optional[str]] = mapped_column(String(128))
    lobby_volume: Mapped[Optional[float]] = mapped_column(Float)
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    creator = relationship("User")
    theme = relationship("Theme", back_populates="packs")
    rounds = relationship("QuestionRound", back_populates="pack", cascade="all, delete", order_by="QuestionRound.round.asc()")
    games = relationship("Game", back_populates="pack", cascade="all", order_by="Game.started_at.asc()")

    __serialize_relationships__ = [creator, rounds, theme]

    @property
    def extra_fields(self):
        return {
            "lobby_music": f"{get_question_pack_data_path(self.id, False)}/{self.lobby_music}" if self.lobby_music else None,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "changed_at": self.changed_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

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
        "name": {"min_length": 1, "pattern": Config.VALID_TITLE_CHARACTERS},
        "round": {"gt": 0, "le": 10},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    name: Mapped[str] = mapped_column(String(64))
    round: Mapped[int] = mapped_column(Integer)

    pack = relationship("QuestionPack", back_populates="rounds")
    categories = relationship("QuestionCategory", back_populates="round", cascade="all, delete", order_by="QuestionCategory.order.asc()")

    __serialize_relationships__ = [categories]

class QuestionCategory(Base):
    __tablename__ = "question_categories"
    __validate_fields__ = {
        "name": {"min_length": 1, "pattern": Config.VALID_TITLE_CHARACTERS},
        "buzz_time": {"ge": 0, "le": 60},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    round_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_rounds.id"))
    name: Mapped[str] = mapped_column(String(64))
    order: Mapped[int] = mapped_column(Integer)
    buzz_time: Mapped[Optional[int]] = mapped_column(Integer, default=10)
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    round = relationship("QuestionRound", back_populates="categories")
    questions = relationship("Question", back_populates="category", cascade="all, delete", order_by="Question.value.asc()")

    __serialize_relationships__ = [questions]

    @property
    def extra_fields(self):
        return {
            "bg_image": None if not self.bg_image else f"{get_question_pack_data_path(self.round.pack_id, False)}/{self.bg_image}",
        }

class Question(Base):
    __tablename__ = "questions"
    __validate_fields__ = {
        "question": {"min_length": 3, "max_length": 128, "pattern": Config.VALID_TITLE_CHARACTERS},
        "answer": {"min_length": 1, "max_length": 128, "pattern": Config.VALID_TITLE_CHARACTERS},
        "value": {"gt": 0, "lt": 10000},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    category_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_categories.id"))
    question: Mapped[str] = mapped_column(String(128))
    answer: Mapped[str] = mapped_column(String(128))
    value: Mapped[int] = mapped_column(Integer)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    category = relationship("QuestionCategory", back_populates="questions")
    game_questions = relationship("GameQuestion", back_populates="question", cascade="all, delete", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")

    @property
    def extra_fields(self):
        if self.extra is None:
            return {"extra": {}}

        fields = dict(self.extra)

        for key in ("question_image", "video", "answer_image"):
            if key in self.extra:
                fields[key] = f"{get_question_pack_data_path(self.category.round.pack_id, False)}/{self.extra[key]}"

        return {"extra": fields}

class BuzzerSound(Base):
    __tablename__ = "buzzer_sounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    theme_id: Mapped[str] = mapped_column(String(64), ForeignKey("themes.id"))
    filename: Mapped[str] = mapped_column(String(128))
    correct: Mapped[bool] = mapped_column(Boolean)

    theme = relationship("Theme", back_populates="buzzer_sounds")

    @property
    def extra_fields(self):
        return {"filename": f"{get_buzz_sound_path(self.theme_id, False)}/{self.filename}"}

class Contestant(Base):
    __tablename__ = "contestants"
    __validate_fields__ = {
        "name": {"min_length": 2, "max_length": 16, "pattern": Config.VALID_NAME_CHARACTERS},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(16))
    color: Mapped[str] = mapped_column(String(16))
    avatar: Mapped[Optional[str]] = mapped_column(String(128))
    buzz_sound: Mapped[Optional[str]] = mapped_column(String(128))
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    game_contestants = relationship("GameContestant", back_populates="contestant", cascade="all, delete", order_by="GameContestant.game_id.asc(), GameContestant.contestant_id.asc()")

class GamePowerUp(Base):
    __tablename__ = "game_power_ups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"))
    contestant_id: Mapped[str] = mapped_column(String(64), ForeignKey("game_contestants.id"))
    type: Mapped[PowerUpType] = mapped_column(Enum(PowerUpType))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    contestant = relationship("GameContestant", back_populates="power_ups")

    @property
    def extra_fields(self):
        theme_id = self.contestant.game.pack.theme_id
        icon = f"{self.type.value}_power.png"

        return {
            "icon": f"img/{icon}" if not theme_id else f"{get_theme_path(theme_id, False)}/{icon}"
        }

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
    power_ups = relationship("GamePowerUp", back_populates="contestant", cascade="all, delete", order_by=case(power_up_order_case, value=GamePowerUp.type))

    __serialize_relationships__ = [contestant, power_ups]

    @property
    def extra_fields(self):
        return {
            "name": self.contestant.name,
            "color": self.contestant.color,
            "avatar": self.contestant.avatar,
            "buzz_sound": self.contestant.buzz_sound,
            "bg_image": self.contestant.bg_image,
            "finale_wager": self.finale_wager,
            "finale_answer": self.finale_answer,
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

    __serialize_relationships__ = [question]

class Game(Base):
    __tablename__ = "games"
    __validate_fields__ = {
        "title": {"min_length": 3, "pattern": Config.VALID_TITLE_CHARACTERS},
        "password": {"min_length": 3, "max_length": 128},
        "regular_rounds": {"gt": 0, "lt": 10},
        "max_contestants": {"gt": 0, "le": 10},
    }

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    title: Mapped[str] = mapped_column(String(32))
    join_code: Mapped[str] = mapped_column(String(64))
    regular_rounds: Mapped[int] = mapped_column(Integer, default=Config.REGULAR_ROUNDS)
    max_contestants: Mapped[int] = mapped_column(Integer)
    answer_time: Mapped[int] = mapped_column(Integer, default=Config.DEFAULT_ANSWER_TIME)
    use_daily_doubles: Mapped[bool] = mapped_column(Boolean, default=True)
    use_powerups: Mapped[bool] = mapped_column(Boolean, default=True)
    stage: Mapped[StageType] = mapped_column(Enum(StageType), default=StageType.LOBBY)
    round: Mapped[int] = mapped_column(Integer, default=1)
    password: Mapped[Optional[str]] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    creator = relationship("User")
    pack = relationship("QuestionPack", back_populates="games")
    game_questions = relationship("GameQuestion", back_populates="game", cascade="all, delete", order_by="GameQuestion.question_id.asc()")
    game_contestants = relationship("GameContestant", back_populates="game", cascade="all, delete", order_by="GameContestant.joined_at.asc()")

    __serialize_relationships__ = [pack, game_questions, game_contestants]

    @property
    def extra_fields(self):
        player_with_turn = self.get_contestant_with_turn()
        questions_for_round = self.get_questions_for_round()

        theme_id = self.pack.theme_id
        theme_dict = {}
        if theme_id:
            data_path = f"{get_theme_path(theme_id, False)}"
            bg_image = f"{data_path}/presenter_background.jpg"
            logo = f"{data_path}/logo.webp"

            theme_dict = {
                "data_path": data_path,
                "template_path": f"themes/{theme_id}",
                "bg_image": bg_image if os.path.exists(f"{Config.STATIC_FOLDER}/{bg_image}") else None,
                "logo": logo if os.path.exists(f"{Config.STATIC_FOLDER}/{logo}") else None,
            }

        # Power-up videos
        language = self.pack.theme.language.value if theme_id else Language.ENGLISH.value

        power_videos = {}
        for power_up in PowerUpType:
            video = f"{power_up.value}_power_used"
            power_videos[power_up.value] = f"img/{video}_{language}.webm" if not theme_id else f"{get_theme_path(theme_id, False)}/{video}.webm",

        return {
            "total_rounds": self.regular_rounds + 1 if self.pack and self.pack.include_finale else self.regular_rounds,
            "player_with_turn": player_with_turn.dump() if player_with_turn else None,
            "max_value": max(gq.question.value for gq in questions_for_round) if questions_for_round else 0,
            "question_num": sum(1 if gq.used else 0 for gq in self.game_questions) + 1,
            "created_by": self.created_by,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": None if not self.ended_at else self.ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            "power_ups": power_videos,
            "theme": theme_dict,
        }

    def get_contestant(self, *, contestant_id: str | None = None, game_contestant_id: str | None = None) -> GameContestant | None:
        if contestant_id is None and game_contestant_id is None:
            return None

        for contestant in self.game_contestants:
            if contestant_id is not None and contestant.contestant_id == contestant_id:
                return contestant

            elif game_contestant_id is not None and contestant.id == game_contestant_id:
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
            key=lambda x: (-x.score, x.contestant.name),
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
