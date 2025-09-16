from typing import Any, Dict, List, Tuple
from os.path import basename

from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename
import flask

from mhooge_flask.routing import make_template_context

from api.config import Config

_UPPERCASE = [chr(i) for i in range(65, 91)]
_LOWERCASE = [chr(x) for x in range(97, 123)]
_NUMBERS = [str(i) for i in range(0, 10)]
_EXTRA = ["_", "-", "'", ""]
VALID_NAME_CHARACTERS = set(_UPPERCASE + _LOWERCASE + _NUMBERS + _EXTRA)

def redirect_to_login(endpoint: str, **params):
    return flask.redirect(flask.url_for("login.login", redirect_page=endpoint, **params, _external=True))

def render_locale_template(template: str, language: str | None = None, status=200, **variables):
    if language is not None:
        locale_data = flask.current_app.config["LOCALES"].get(language.value)
        page_key = template.split(".")[0]
        if locale_data:
            page_data = locale_data["pages"].get(page_key, {})
            page_data.update(locale_data["pages"].get("global", {}))
            variables["_locale"] = page_data

    return make_template_context(template, status, **variables)

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

def validate_file(file: FileStorage, valid_types: List[str], validate_name: bool = True):
    if not file.filename:
        return False, "File name is empty"

    file_type = file.filename.split(".")[-1]
    if file_type not in valid_types:
        return False, f"File is not a valid type (must be one of: {valid_types})"

    if validate_name:
        secure_name = secure_filename(file.filename)
        if secure_name == "":
            return False, "Filename contains invalid characters"

        for c in basename(secure_name):
            if c.strip() not in VALID_NAME_CHARACTERS:
                return False, f"Filename contains an invalid character: {c}"
    else:
        secure_name = None

    return True, secure_name

def get_data_path_for_question_pack(pack_id: str, full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/{pack_id}"

def get_avatar_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/avatars"

def get_buzz_sound_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/sounds"

def get_bg_image_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/backgrounds"
