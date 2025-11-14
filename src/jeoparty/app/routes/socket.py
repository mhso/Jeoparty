from collections.abc import Callable
import json
from multiprocessing import Lock
from time import sleep, time
from typing import Dict, List
from dataclasses import dataclass, field

import flask
from flask_socketio import Namespace

from mhooge_flask.logging import logger

from jeoparty.api.database import Database
from jeoparty.api.enums import PowerUpType
from jeoparty.api.orm.models import Game

_PING_SAMPLES = 10

@dataclass
class GameMetadata:
    question_asked_time: float = field(default=0, init=False)
    buzz_winner_decided: bool = field(default=False, init=False)
    power_use_decided: bool = field(default=False, init=False)

@dataclass
class ContestantMetadata:
    sid: str
    ping: float = 30
    latest_buzz: float | None = field(init=False, default=None)
    _ping_samples: List[float] = field(init=False, default_factory=list)
    
    def calculate_ping(self, time_sent: float, time_received: float):
        if self._ping_samples is None:
            self._ping_samples = []

        self._ping_samples.append((time_received - time_sent) / 2)
        self.ping = sum(self._ping_samples) / _PING_SAMPLES

        if len(self._ping_samples) == _PING_SAMPLES:
            self._ping_samples.pop(0)

def _presenter_event(func):
    def wrapper(*args, **kwargs):
        instance = args[0]
        if not "presenter" in instance.rooms(flask.request.sid):
            raise RuntimeError(f"User does not have permission to emit event '{func.__name__}'")

        # Fetch fresh copy of game data
        with instance.database:
           instance.game_data = instance.database.get_game_from_id(instance.game_id)
           return func(*args, **kwargs)
    
    return wrapper

def _contestants_event(func):
    def wrapper(*args, **kwargs):
        instance = args[0]
        if not "contestants" in instance.rooms(flask.request.sid):
            raise RuntimeError(f"User does not have permission to emit event '{func.__name__}'")

        # Fetch fresh copy of game data
        with instance.database:
           instance.game_data = instance.database.get_game_from_id(instance.game_id)
           return func(*args, **kwargs)

    return wrapper

class GameSocketHandler(Namespace):
    def __init__(self, game_id: str):
        super().__init__(f"/{game_id}")
        self.game_id = game_id
        self.game_data: Game | None = None
        self.database: Database = flask.current_app.config["DATABASE"]
        self.game_metadata = GameMetadata()
        self.contestant_metadata: Dict[str, ContestantMetadata] = {}
        self.buzz_lock = Lock()
        self.power_lock = Lock()

    def emit(
        self,
        event: str,
        data=None,
        to: str | None = None,
        include_self: bool = True,
        namespace: str | None = None,
        skip_sid: str | List[str] | None = None,
        callback: Callable | None = None
    ):
        if to is None:
            to = flask.request.sid

        return self.socketio.emit(
            event,
            data,
            room=to,
            include_self=include_self,
            namespace=namespace or self.namespace,
            skip_sid=skip_sid,
            callback=callback
        )

    def on_presenter_join(self, user_id: str):
        with self.database:
            game_data = self.database.get_game_from_id(self.game_id)

            if game_data.created_by != user_id:
                logger.warning(
                    f"User '{user_id}' tried to join 'presenter' room, "
                    f"but is not the creator of the game with ID '{self.game_id}'."
                )
                return

            self.enter_room(flask.request.sid, "presenter")

            print("Presenter joined")

            self.emit("presenter_joined", to=flask.request.sid)

    def on_contestant_join(self, user_id: str):
        with self.database:
            game_data = self.database.get_game_from_id(self.game_id)
    
            game_contestant = game_data.get_contestant(game_contestant_id=user_id)
            if game_contestant is None:
                logger.warning(
                    f"User '{user_id}' tried to join 'contestant' room, "
                    f"but is not a game contestant for game with ID '{self.game_id}'."
                )
                return

            sid = flask.request.sid
            self.contestant_metadata[user_id] = ContestantMetadata(sid)

            contestant_data = game_contestant.extra_fields
    
            # Add socket IO session ID to contestant and join 'contestants' room
            print(f"User '{contestant_data['name']}' with ID '{user_id}' and SID '{sid}' joined the lobby")
            self.leave_room(sid, "contestants")
            self.enter_room(sid, "contestants")

            self.emit("contestant_joined", (user_id, contestant_data["name"], contestant_data["avatar"], contestant_data["color"]), to="presenter")
            self.emit("contestant_joined", to=sid)

    @_presenter_event
    def on_mark_question_active(self, question_id: str):
        question = self.game_data.get_question(question_id)
        question.active = True

        self.database.save_models(question)

    @_presenter_event
    def on_enable_buzz(self, active_players_string: str):
        active_player_ids = json.loads(active_players_string)

        active_ids = []
        for contestant_id in self.contestant_metadata:
            contestant_metadata = self.contestant_metadata[contestant_id]
            contestant_metadata.latest_buzz = None
            if active_player_ids[contestant_id]:
                active_ids.append(contestant_id)

        self.game_metadata.buzz_winner_decided = False
        self.game_metadata.question_asked_time = time()

        self.emit("buzz_enabled", active_ids, to="contestants")

    @_presenter_event
    def on_enable_powerup(self, user_id: str | None, power_id: str):
        if user_id is not None:
            player_ids = [user_id]

        else:
            player_ids = [contestant_id for contestant_id in self.contestant_metadata]

        skip_contestants = []
        power_up_models = []
        for contestant_id in player_ids:
            contestant = self.game_data.get_contestant(game_contestant_id=contestant_id)
            metadata = self.contestant_metadata[contestant_id]
            power_up = contestant.get_power(PowerUpType(power_id))
            if power_up.used:
                skip_contestants.append(metadata.sid)
                continue

            power_up.enabled = True
            power_up_models.append(power_up)

        self.game_metadata.power_use_decided = False

        if skip_contestants != [] and user_id is not None:
            return

        self.database.save_models(*power_up_models)

        send_to = self.contestant_metadata[user_id].sid if user_id is not None else "contestants"
        self.emit("power_up_enabled", power_id, to=send_to, skip_sid=skip_contestants)

    @_presenter_event
    def on_disable_powerup(self, user_id: str | None, power_id: str | None):
        if user_id is not None:
            player_ids = [user_id]

        else:
            player_ids = [contestant_id for contestant_id in self.contestant_metadata]

        power_ups = [PowerUpType(power_id)] if power_id is not None else list(PowerUpType)
        power_up_models = []
        for contestant_id in player_ids:
            contestant = self.game_data.get_contestant(game_contestant_id=contestant_id)
            for power_up in power_ups:
                power = contestant.get_power(power_up)
                power.enabled = False
                power_up_models.append(power)

        self.game_metadata.power_use_decided = True

        self.database.save_models(*power_up_models)

        send_to = self.contestant_metadata[user_id].sid if user_id is not None else "contestants"
        self.emit("power_ups_disabled", [power_up.value for power_up in power_ups], to=send_to)

    @_presenter_event
    def on_correct_answer(self, user_id: str, value: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        contestant_metadata = self.contestant_metadata[user_id]

        player_with_turn = self.game_data.get_contestant_with_turn()

        contestant_data.hits += 1
        contestant_data.score += value
        contestant_data.has_turn = True
        models_to_save = [contestant_data]

        if player_with_turn is not None and player_with_turn.id != contestant_data.id:
            player_with_turn.has_turn = False
            models_to_save.append(player_with_turn)

        self.database.save_models(*models_to_save)

        contestant_info = {
            "hits": contestant_data.hits,
            "score": contestant_data.score,
        }
        self.emit("contestant_info_changed", json.dumps(contestant_info), to=contestant_metadata.sid)

    @_presenter_event
    def on_wrong_answer(self, user_id: int, value: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        contestant_metadata = self.contestant_metadata[user_id]

        contestant_data.misses += 1
        contestant_data.score -= value

        self.database.save_models(contestant_data)

        contestant_info = {
            "misses": contestant_data.misses,
            "score": contestant_data.score,
        }
        self.emit("contestant_info_changed", json.dumps(contestant_info), to=contestant_metadata.sid)

    @_presenter_event
    def on_disable_buzz(self):
        self.game_metadata.buzz_winner_decided = True

        self.emit("buzz_disabled", to="contestants")

    @_presenter_event
    def on_first_turn(self, user_id: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)

        player_with_turn = self.game_data.get_contestant_with_turn()

        contestant_data.has_turn = True
        models_to_save = [contestant_data]

        if player_with_turn is not None:
            player_with_turn.has_turn = False
            models_to_save.append(player_with_turn)

        self.database.save_models(*models_to_save)

        self.emit("turn_chosen", user_id, to="contestants")

    @_contestants_event
    def on_use_power_up(self, user_id: str, power_id: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        contestant_metadata = self.contestant_metadata[user_id]
        power = PowerUpType(power_id)

        print(f"Power up '{power}' used by {contestant_data.contestant.name}", flush=True)

        with self.power_lock:
            if self.game_metadata.power_use_decided:
                return

            self.game_metadata.power_use_decided = True

            power_up = contestant_data.get_power(power)
            if power_up.used: # Contestant has already used this power_up
                return

            power_up.used = True

            self.database.save_models(contestant_data, power_up)

            if power_id in (PowerUpType.HIJACK, PowerUpType.REWIND):
                self.emit("buzz_disabled", to="contestants", skip_sid=contestant_metadata.sid)

            self.emit("power_ups_disabled", [power.value for power in PowerUpType], to="contestants")
            self.emit("power_up_used", (user_id, power_id), to="presenter")
            self.emit("power_up_used", power_id, to=contestant_metadata.sid)

    @_presenter_event
    def on_rewind_used(self, user_id: str, value: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)

        # Refund points lost from wrong answer when rewind is used
        contestant_data.score += value
        contestant_data.misses -= 1

        self.database.save_models(contestant_data)

    @_presenter_event
    def on_enable_finale_wager(self):
        self.emit("finale_wager_enabled", to="contestants")

    @_presenter_event
    def on_enable_finale_answer(self):
        self.emit("finale_answer_enabled", to="contestants")

    @_contestants_event
    def on_buzzer_pressed(self, user_id: str):
        contestant_metadata = self.contestant_metadata[user_id]
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)

        if contestant_metadata.latest_buzz is not None:
            # Player already buzzed in this round, simply return
            return

        contestant_metadata.latest_buzz = time() - (contestant_metadata.ping / 1000)
        time_taken = f"{contestant_metadata.latest_buzz - self.game_metadata.question_asked_time:.2f}"
        contestant_data.buzzes += 1

        self.emit("buzz_received", (user_id, time_taken), to="presenter")
        self.emit("buzz_received", to=contestant_metadata.sid)

        print(
            f"Buzz from {contestant_data.contestant.name} ({contestant_metadata.sid}):",
            f"{contestant_metadata.latest_buzz}, ping: {contestant_metadata.ping}",
            flush=True
        )

        sleep(min(max(max(c.ping / 1000, 0.01) for c in self.contestant_metadata.values()), 1))

        # Make sure no other requests can declare a winner by using a lock
        with self.buzz_lock:
            if self.game_metadata.buzz_winner_decided:
                return

            self.game_metadata.buzz_winner_decided = True

            earliest_buzz_time = time()
            earliest_buzz_id = None
            for cont_id in self.contestant_metadata:
                cont_metadata = self.contestant_metadata[cont_id]
                if cont_metadata.latest_buzz is not None and cont_metadata.latest_buzz < earliest_buzz_time:
                    earliest_buzz_time = cont_metadata.latest_buzz
                    earliest_buzz_id = cont_id

            # Reset buzz-in times
            for c in self.contestant_metadata.values():
                c.latest_buzz = None

            earliest_buzz_player = self.contestant_metadata[earliest_buzz_id]

            print("Earliest buzz:", earliest_buzz_player.sid, earliest_buzz_time)

            self.emit("buzz_winner", to=earliest_buzz_player.sid)
            self.emit("buzz_winner", earliest_buzz_id, to="presenter")
            self.emit("buzz_loser", to="contestants", skip_sid=earliest_buzz_player.sid)

            self.database.save_models(contestant_data)

    @_presenter_event
    def on_undo_answer(self, user_id: str, value: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        contestant_metadata = self.contestant_metadata[user_id]

        if value < 0:
            contestant_data.hits -= 1
        else:
            contestant_data.misses -= 1

        contestant_data.score += value

        self.database.save_models(contestant_data)

        self.emit("buzz_disabled", to="contestants", skip_sid=contestant_metadata.sid)

    @_presenter_event
    def on_edit_contestant_info(self, user_id: str, json_str: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        contestant_metadata = self.contestant_metadata[user_id]
        data = json.loads(json_str)

        keys = ["hits", "misses", "score"]
        for key in keys:
            if key in data:
                setattr(contestant_data, key,  data[key])

        if (powers := data.get("powers")):
            for power in contestant_data.power_ups:
                used = powers.get(power.type.value)
                if used is not None:
                    power.used = used

        self.database.save_models(contestant_data)

        self.emit("contestant_info_changed", json_str, to=contestant_metadata.sid)

    @_contestants_event
    def on_ping_request(self, user_id: str, timestamp: float):
        self.emit("ping_response", (user_id, timestamp))

    @_contestants_event
    def on_calculate_ping(self, user_id: str, timestamp_sent: float, timestamp_received: float):
        contestant_metadata = self.contestant_metadata[user_id]
        contestant_metadata.calculate_ping(timestamp_sent, timestamp_received)

        self.emit("ping_calculated", f"{min(999.0, max(contestant_metadata.ping, 1.0)):.1f}")

    @_contestants_event
    def on_make_daily_wager(self, user_id: str, amount: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)

        min_wager = 100
        max_wager = max(contestant_data.score, 500 * self.game_data.round)

        try:
            amount = int(amount)
        except ValueError:
            self.emit("invalid_wager", (min_wager, max_wager))
            return

        if min_wager <= amount <= max_wager:
            self.emit("daily_wager_made", amount)
            self.emit("daily_wager_made", amount, to="presenter")
        else:
            self.emit("invalid_wager", (min_wager, max_wager))

    @_contestants_event
    def on_make_finale_wager(self, user_id: str, amount: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)

        min_wager = 0
        max_wager = max(contestant_data.score, 1000)

        try:
            amount = int(amount)
        except ValueError:
            self.emit("invalid_wager", (min_wager, max_wager))
            return

        if min_wager <= amount <= max_wager:
            print(f"Made finale wager for {user_id} ({contestant_data.contestant.name}) for {amount} points")
            contestant_data.finale_wager = amount

            self.database.save_models(contestant_data)

            self.emit("finale_wager_made")
            self.emit("contestant_ready", user_id, to="presenter")
        else:
            self.emit("invalid_wager", (min_wager, max_wager))

    @_contestants_event
    def on_give_finale_answer(self, user_id: str, answer: str):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        if not contestant_data.finale_wager:
            return

        contestant_data.finale_answer = answer

        self.database.save_models(contestant_data)

        self.emit("finale_answer_given")
        self.emit("contestant_ready", user_id, to="presenter")

    @_presenter_event
    def on_finale_answer_correct(self, user_id: str, amount: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        if not contestant_data.finale_wager:
            return

        contestant_data.score += amount
        contestant_data.hits += 1

        self.database.save_models(contestant_data)

    @_presenter_event
    def on_finale_answer_wrong(self, user_id: str, amount: int):
        contestant_data = self.game_data.get_contestant(game_contestant_id=user_id)
        if not contestant_data.finale_wager:
            return

        contestant_data.score -= amount
        contestant_data.misses += 1

        self.database.save_models(contestant_data)
