from typing import Any, Dict, Tuple
import flask

from api.config import STATIC_FOLDER

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

def get_data_path_for_question_pack(pack_id: str, full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/{pack_id}"

def get_avatar_path(full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/avatars"

def get_bg_image_path(full: bool = True):
    prefix = f"{STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/backgrounds"
