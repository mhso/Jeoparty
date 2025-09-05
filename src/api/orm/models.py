from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship, reconstructor

from api.orm.base import Base
from api.enums import Stage, PowerUp
from api.config import REGULAR_ROUNDS
from app.routes.shared import get_avatar_path

class QuestionPack(Base):
    __tablename__ = "question_packs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    include_finale: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    rounds = relationship("QuestionRound", back_populates="pack", cascade="all, delete-orphan", order_by="QuestionRound.round.asc()")
    games = relationship("Game", back_populates="pack", cascade="all, delete-orphan", order_by="Game.started_at.asc()")
    buzzer_sounds = relationship("BuzzerSound", back_populates="pack", cascade="all, delete-orphan", order_by="BuzzerSound.id.asc()")

    def get_all_questions(self):
        questions = []
        for round_data in self.rounds:
            for category_data in round_data.categories:
                for question_data in category_data.questions:
                    questions.append(question_data)

        return questions

class QuestionRound(Base):
    __tablename__ = "question_rounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    name: Mapped[str] = mapped_column(String(64))
    round: Mapped[int] = mapped_column(Integer)

    pack = relationship("QuestionPack", back_populates="rounds")
    categories = relationship("QuestionCategory", back_populates="round", cascade="all, delete-orphan", order_by="QuestionCategory.order.asc()")

class QuestionCategory(Base):
    __tablename__ = "question_categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    round_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_rounds.id"))
    name: Mapped[str] = mapped_column(String(64))
    order: Mapped[int] = mapped_column(Integer)
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    round = relationship("QuestionRound", back_populates="categories")
    questions = relationship("Question", back_populates="category", cascade="all, delete-orphan", order_by="Question.value.asc()")

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    category_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_categories.id"))
    question: Mapped[str] = mapped_column(String(128))
    answer: Mapped[str] = mapped_column(String(128))
    value: Mapped[int] = mapped_column(Integer)
    buzz_time: Mapped[int] = mapped_column(Integer)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    category = relationship("QuestionCategory", back_populates="questions")
    game_questions = relationship("GameQuestion", back_populates="question", cascade="all, delete-orphan", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")

class BuzzerSound(Base):
    __tablename__ = "buzzer_sounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"), primary_key=True)
    path: Mapped[str] = mapped_column(String(128))
    correct: Mapped[bool] = mapped_column(Boolean)

    pack = relationship("QuestionPack", back_populates="buzzer_sounds")

class Contestant(Base):
    __tablename__ = "contestants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(16))
    avatar: Mapped[Optional[str]] = mapped_column(String(128))
    buzz_sound: Mapped[Optional[str]] = mapped_column(String(128))
    bg_image: Mapped[Optional[str]] = mapped_column(String(128))

    game_contestants = relationship("GameContestant", back_populates="contestant", cascade="all, delete-orphan", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")

    @property
    def extra_fields(self):
        return {
            "avatar": f"{get_avatar_path()}/{self.avatar}"
        }

class GamePowerUp(Base):
    __tablename__ = "game_power_ups"

    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"), primary_key=True)
    contestant_id: Mapped[str] = mapped_column(String(64), ForeignKey("game_contestants.id"), primary_key=True)
    power_up: Mapped[PowerUp] = mapped_column(Enum(PowerUp), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    contestant = relationship("GameContestant", back_populates="power_ups")

class GameContestant(Base):
    __tablename__ = "game_contestants"

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
    power_ups = relationship("GamePowerUp", back_populates="contestant", cascade="all, delete-orphan", order_by="GamePowerUp.power_up.asc()")

    def __init__(self, **kw: Any):
        super().__init__(**kw)

    @reconstructor
    def init_on_load(self):
        self.ping = 30
        self.n_ping_samples = 10
        self.latest_buzz = None
        self._ping_samples = []

    def calculate_ping(self, time_sent, time_received):
        if self._ping_samples is None:
            self._ping_samples = []

        self._ping_samples.append((time_received - time_sent) / 2)
        self.ping = sum(self._ping_samples) / self.n_ping_samples

        if len(self._ping_samples) == self.n_ping_samples:
            self._ping_samples.pop(0)

    def get_power(self, power: PowerUp) -> GamePowerUp | None:
        for power_up in self.power_ups:
            if power_up.power_up is power:
                return power_up

        return None

class GameQuestion(Base):
    __tablename__ = "game_questions"

    game_id: Mapped[str] = mapped_column(String(64), ForeignKey("games.id"), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("questions.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_double: Mapped[bool] = mapped_column(Boolean, default=False)

    game = relationship("Game", back_populates="questions")
    question = relationship("Question", back_populates="game_questions")

class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    pack_id: Mapped[str] = mapped_column(String(64), ForeignKey("question_packs.id"))
    title: Mapped[str] = mapped_column(String(64))
    regular_rounds: Mapped[int] = mapped_column(Integer, default=REGULAR_ROUNDS)
    max_contestants: Mapped[int] = mapped_column(Integer)
    use_daily_doubles: Mapped[bool] = mapped_column(Boolean, default=True)
    use_powerups: Mapped[bool] = mapped_column(Boolean, default=True)
    stage: Mapped[Stage] = mapped_column(Enum(Stage), default=Stage.LOBBY)
    round: Mapped[int] = mapped_column(Integer, default=0)
    password: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now())

    pack = relationship("QuestionPack", back_populates="games")
    questions = relationship("GameQuestion", back_populates="game", cascade="all, delete-orphan", order_by="GameQuestion.game_id.asc(), GameQuestion.question_id.asc()")
    game_contestants = relationship("GameContestant", back_populates="game", cascade="all, delete-orphan", order_by="GameContestant.joined_at.asc()")

    @property
    def extra_fields(self):
        player_with_turn = self.get_contestant_with_turn()

        return {
            "total_rounds": self.regular_rounds + 1 if self.pack and self.pack.include_finale else self.regular_rounds,
            "player_with_turn": player_with_turn.json if player_with_turn else None,
            "max_value": max(gq.question.value for gq in self.get_questions_for_round()) if self.questions else 0,
        }

    def get_contestant(self, contestant_id: str | None) -> GameContestant | None:
        if contestant_id is None:
            return None

        for contestant in self.game_contestants:
            if contestant.contestant_id == contestant_id:
                return contestant

        return None

    def get_question(self, question_id: str) -> GameQuestion | None:
        for question in self.questions:
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
            game_question for game_question in self.questions
            if game_question.question.category.round == self.round
        ]

    def get_active_question(self) -> GameQuestion | None:
        for question in self.questions:
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
