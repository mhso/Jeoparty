from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import flask

from api.config import STATIC_FOLDER
from api.orm.models import GameContestant

_PING_SAMPLES = 10

@dataclass
class ContestantMetadata:
    ping: float = 30
    latest_buzz: int | None = field(init=False, default=None)
    _ping_samples: List[float] = field(init=False, default_factory=list)
    
    def calculate_ping(self, time_sent: float, time_received: float):
        if self._ping_samples is None:
            self._ping_samples = []

        self._ping_samples.append((time_received - time_sent) / 2)
        self.ping = sum(self._ping_samples) / _PING_SAMPLES

        if len(self._ping_samples) == _PING_SAMPLES:
            self._ping_samples.pop(0)

def get_contestant_metadata(config: Dict[str, Any], game_id: str, contestant_id: str) -> ContestantMetadata:
    data = config["CONTESTANT_METADATA"].get(game_id, {}).get(contestant_id)
    if data is None:
        if game_id not in config["CONTESTANT_METADATA"]:
            config["CONTESTANT_METADATA"][game_id] = {}

        data = ContestantMetadata()
        config["CONTESTANT_METADATA"][game_id][contestant_id] = data

    return data

def redirect_to_login(endpoint: str, **params):
    return flask.redirect(flask.url_for("login.sign_in", redirect=endpoint, **params, _external=True))

def validate_param(
    params: Dict[str, Any],
    key: str,
    dtype: type,
    min_len: int = None,
    max_len: int = None
) -> Tuple[Any, str | None]:
    if key not in params:
        return None, f"'{key.capitalize()}' is required"

    try:
        val = dtype(params[key])
    except TypeError:
        type_name = "text" if dtype == type(str) else "a number"
        return None, f"'{key}' must be {type_name}"

    if min_len is not None:
        if isinstance(val, (int, float)) and val < min_len:
            return None, f"'{key.capitalize()}' must be larger than {min_len}"
        elif isinstance(val, str) and len(val) < min_len:
            return None, f"'{key.capitalize()}' must be longer than {min_len} characters"
        
    if max_len is not None:
        if isinstance(val, (int, float)) and val > max_len:
            return None, f"'{key.capitalize()}' must be less than {max_len}"
        elif isinstance(val, str) and len(val) > max_len:
            return None, f"'{key.capitalize()}' must be less than {max_len} characters"

    return val, None

def get_game_winner(contestants: List[GameContestant]):
    pass

def get_data_path_for_question_pack(pack_id: str, full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/{pack_id}"

def get_avatar_path(full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/avatars"

def get_bg_image_path(full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/backgrounds"
