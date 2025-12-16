from glob import glob
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

from jeoparty.api.config import Config, get_theme_path, file_or_fallback
from jeoparty.api.enums import Language
from jeoparty.api.orm.models import Game, Theme

def redirect_to_login(endpoint: str, **params):
    return flask.redirect(flask.url_for("login.login", redirect_page=endpoint, **params, _external=True))

def get_locale_data(language: Language, page: str):
    locale_data = flask.current_app.config["LOCALES"].get(language.value)
    if locale_data:
        page_data = locale_data["pages"].get(page, {})
        page_data.update(locale_data["pages"].get("global", {}))
        return page_data
    
    return None

def render_locale_template(template: str, lang_code: Language | None = None, status=200, **variables):
    if lang_code is not None:
        page_key = template.split(".")[0]
        page_data = get_locale_data(lang_code, page_key)
        if page_data:
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

def get_question_answer_sounds(theme: Theme, max_contestants: int):
    default_correct = "data/sounds/correct_answer.mp3"
    if theme:
        correct_sounds = [
            f"{get_theme_path(theme.id, False)}/sounds/{sound.filename}"
            for sound in theme.buzzer_sounds
            if sound.correct
        ]
        if correct_sounds == []:
            correct_sound = default_correct
        else:
            correct_sound = random.choice(correct_sounds)
    else:
        # Get default correct answer sound
        correct_sound = default_correct

    default_wrong = "data/sounds/wrong_answer.mp3"
    if theme:
        wrong_sounds = [
            f"{get_theme_path(theme.id, False)}/sounds/{sound.filename}"
            for sound in theme.buzzer_sounds
            if not sound.correct
        ]
    else:
        wrong_sounds = []

    # Get as many wrong sounds as there are contestants, adding in default sounds
    # if we don't have enough custom ones
    if len(wrong_sounds) < max_contestants:
        # Add default wrong answer sound
        wrong_sounds = wrong_sounds + [default_wrong for _ in range(max_contestants - len(wrong_sounds))]

    random.shuffle(wrong_sounds)
    wrong_sounds = wrong_sounds[:max_contestants]

    return correct_sound, wrong_sounds

def get_question_answer_images(theme: Theme):
    default_correct = "img/check.png"
    default_wrong = "img/error.png"

    if theme:
        correct_images = glob(f"{get_theme_path(theme.id)}/correct_icons/*")
        wrong_images = glob(f"{get_theme_path(theme.id)}/wrong_icons/*")
        if correct_images == []:
            correct_image = default_correct
        else:
            correct_image = random.choice(correct_images).split("static/")[1]

        if wrong_images == []:
            wrong_image = default_wrong
        else:
            wrong_image = random.choice(wrong_images).split("static/")[1]
    else:
        correct_image = default_correct
        wrong_image = default_wrong

    return correct_image, wrong_image

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

            if value is not None and (column.type.python_type is int or column.type.python_type is float):
                value = column.type.python_type(value)

            elif column.type.python_type is bool:
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
