import os
import random
import traceback
from enum import Enum
from typing import Any, Dict, List, Tuple, TypeVar
from os.path import basename

from pydantic_core import ErrorDetails
from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename
from pydantic import ValidationError
import flask

from mhooge_flask.routing import make_template_context
from mhooge_flask.database import Base

from jeoparty.api.config import Config, get_theme_path
from jeoparty.api.enums import Language
from jeoparty.api.orm.models import Game, Question, QuestionPack

def redirect_to_login(endpoint: str, **params):
    return flask.redirect(flask.url_for("login.login", redirect_page=endpoint, **params, _external=True))

def render_locale_template(template: str, lang_code: Language | None = None, status=200, **variables):
    if lang_code is not None:
        locale_data = flask.current_app.config["LOCALES"].get(lang_code.value)
        page_key = template.split(".")[0]
        if locale_data:
            page_data = locale_data["pages"].get(page_key, {})
            page_data.update(locale_data["pages"].get("global", {}))
            variables["_locale"] = page_data

    return make_template_context(template, status, **variables)

def dump_game_to_json(game_data: Game):
    game_json = game_data.dump(id="game_id")
    game_json["pack"] = game_json.pack.dump()
    game_json["game_contestants"] = []

    # Handle contestants and their power-ups
    for contestant_data in game_data.game_contestants:
        contestant_json = contestant_data.dump()
        del contestant_json["game"]
        game_json["game_contestants"].append(contestant_json)

    return game_json

def get_question_answer_sounds(pack: QuestionPack, max_contestants: int):
    if pack.theme_id:
        correct_sounds = [
            f"{get_theme_path(pack.theme_id, False)}/sounds/{sound.filename}"
            for sound in pack.theme.buzzer_sounds
            if sound.correct
        ]
        correct_sound = random.choice(correct_sounds)
    else:
        # Get default correct answer sound
        correct_sound = "data/sounds/correct_answer.mp3"

    if pack.theme_id:
        wrong_sounds = [
            f"{get_theme_path(pack.theme_id, False)}/sounds/{sound.filename}"
            for sound in pack.theme.buzzer_sounds
            if not sound.correct
        ]
    else:
        wrong_sounds = []

    # Get as many wrong sounds as there are contestants, adding in default sounds
    # if we don't have enough custom ones
    if len(wrong_sounds) < max_contestants:
        # Add default wrong answer sound
        wrong_sounds = wrong_sounds + ["data/sounds/wrong_answer.mp3" for _ in range(max_contestants - len(wrong_sounds))]

    random.shuffle(wrong_sounds)
    wrong_sounds = wrong_sounds[:max_contestants]

    return correct_sound, wrong_sounds

def get_question_answer_images(pack: QuestionPack):
    if pack.theme_id:
        data_path = get_theme_path(pack.theme_id, False)
    else:
        data_path = None

    if data_path is not None and os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "correct_answer.png")):
        correct_image = f"{data_path}/correct_answer.png"
    else:
        correct_image = "img/check.png"

    if data_path is not None and os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "wrong_answer.png")):
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
    correct_image, wrong_image = get_question_answer_images(game_data.pack)

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

T = TypeVar("T", bound="Base")

def get_validation_error_msg(detail: ErrorDetails):
    loc_fmt = detail["loc"][0].replace("_", " ").capitalize()

    if detail["type"] == "string_pattern_mismatch":
        return f"'{loc_fmt}' contains invalid characters"

    if detail["type"] in ("string_too_long", "string_too_short"):
        return f"'{loc_fmt}' {detail['msg'].replace('String ', '')}"

    return f"'{loc_fmt}' - {detail['msg']}"

def create_and_validate_model(model_cls: type[T], data: Dict[str, Any], action: str) -> Tuple[bool, T | str]:
    try:
        model_data = {}
        for column in model_cls.__table__.columns:
            value = data.get(column.name)

            if column.type.python_type is bool:
                if value == "on":
                    value = True
                elif value == "off":
                    value = False
                elif value is None:
                    value = False

            elif column.type.python_type.__base__ is Enum and value is not None:
                try:
                    enum = column.type.python_type(value)
                except AttributeError:
                    continue

                value = enum

            elif column.type.python_type is str and value == "":
                value = None

            if value is not None:
                model_data[column.name] = value

        return True, model_cls(**model_data)

    except ValidationError as exc:
        traceback.print_exc()
        details = ", ".join([get_validation_error_msg(detail) for detail in exc.errors(include_url=False)])
        message = f"Error when {action}: {details}"

        return False, message

def validate_file(
    file: FileStorage,
    path: str,
    valid_types: List[str],
    default_name: str | None = None,
    allow_overwrite: bool = False,
):
    if not file.filename:
        return False, "File name is empty"

    file_type_split = file.filename.split(".")
    file_type = file_type_split[-1].lower()
    if file_type not in valid_types:
        return False, f"File is not a valid type (must be one of: {valid_types})"

    if default_name is None:
        filename = f"{file_type_split[0]}.{file_type_split[-1].lower()}"
        secure_name = secure_filename(filename)
        if secure_name == "":
            return False, "Filename contains invalid characters"

        if Config.VALID_NAME_CHARACTERS.match(basename(secure_name.split(".")[0])) is None:
            return False, f"Filename contains an invalid character. Must be of the pattern '{str(Config.VALID_NAME_CHARACTERS)}'"
    else:
        secure_name = default_name    

    # Validate that the file doesn't exist, if so add a suffix to make it unique
    full_path = os.path.join(path, secure_name)
    if not allow_overwrite:
        suffix = 1
        while os.path.exists(full_path):
            split = secure_name.split(".")

            secure_name = f"{split[0]}_{suffix}.{split[1]}"
            full_path = os.path.join(path, secure_name)
            suffix += 1

    return True, full_path
