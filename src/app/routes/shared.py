import os
import random
from typing import Any, Dict, List, Tuple
from os.path import basename

from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename
import flask

from mhooge_flask.routing import make_template_context

from api.config import Config, get_data_path_for_question_pack
from api.orm.models import Game, Question, QuestionPack

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

def dump_game_to_json(game_data: Game):
    game_json = game_data.dump(id="game_id")
    game_json["game_contestants"] = []

    # Handle contestants and their power-ups
    for contestant_data in game_data.game_contestants:
        contestant_json = contestant_data.dump()
        del contestant_json["game"]
        game_json["game_contestants"].append(contestant_json)

    return game_json

def get_question_answer_sounds(pack: QuestionPack, max_contestants: int):
    correct_sounds = [
        f"data/sounds/{sound.filename}"
        for sound in pack.buzzer_sounds if sound.correct
    ]

    if correct_sounds == []:
        # Get default correct answer sound
        correct_sound = "data/sounds/correct_answer.mp3"
    else:
        correct_sound = random.choice(correct_sounds)

    wrong_sounds = [
        f"data/sounds/{sound.filename}"
        for sound in pack.buzzer_sounds if not sound.correct
    ]

    # Get as many wrong sounds as there are contestants, adding in default sounds
    # if we don't have enough custom ones
    if len(wrong_sounds) < max_contestants:
        # Add default wrong answer sound
        wrong_sounds = wrong_sounds + ["data/sounds/wrong_answer.mp3" for _ in range(max_contestants - len(wrong_sounds))]

    random.shuffle(wrong_sounds)
    wrong_sounds = wrong_sounds[:max_contestants]

    return correct_sound, wrong_sounds

def get_question_answer_images(pack_id: str):
    data_path = get_data_path_for_question_pack(pack_id, False)
    if os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "correct_answer.png")):
        correct_image = f"{data_path}/correct_answer.png"
    else:
        correct_image = "img/check.png"

    if os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "wrong_answer.png")):
        wrong_image = f"{data_path}/wrong_answer.png"
    else:
        wrong_image = "img/error.png"

    return correct_image, wrong_image

def render_question_template(game_data: Game, question: Question, daily_double: bool = False):
    question_json = question.dump(id="question_id")
    question_json["daily_double"] = daily_double

    del question_json["game_questions"]

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_json["extra"]:
        random.shuffle(question_json["extra"]["choices"])

    # Get images for when questiton is answered correctly or wrong
    correct_image, wrong_image = get_question_answer_images(game_data.pack.id)

    # Get random sounds that plays for correct/wrong answers
    correct_sound, wrong_sounds = get_question_answer_sounds(game_data.pack, game_data.max_contestants)

    round_name = game_data.pack.rounds[game_data.round - 1].name

    # Get game JSON data with nested contestant data
    game_json = dump_game_to_json(game_data)

    return render_locale_template(
        "presenter/question.html",
        game_data.pack.language,
        correct_image=correct_image,
        wrong_image=wrong_image,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        round_name=round_name,
        **game_json,
        **question_json,
    )

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