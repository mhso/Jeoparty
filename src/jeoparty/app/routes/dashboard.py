import json
import os
from typing import Any, Dict
from pydantic import ValidationError
import requests

import flask
from werkzeug.datastructures import FileStorage

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response, make_json_response
from mhooge_flask.logging import logger

from jeoparty.api.database import Database
from jeoparty.api.config import Config, get_question_pack_data_path
from jeoparty.api.orm.models import *
from jeoparty.api.enums import StageType
from jeoparty.app.routes.shared import (
    redirect_to_login,
    validate_file,
    get_validation_error_msg,
    create_and_validate_model,
    render_locale_template,
)

_VALID_IMAGE_FILETYPES = [
    "image/apng",
    "image/gif",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
]

_VALID_VIDEO_FILETYPES = [
    "video/webm",
    "video/mp4",
]

dashboard_page = flask.Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_page.route("/")
def home():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.home")

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    with database:
        question_data = database.get_question_packs_for_user(user_id)
        questions_json = []
        for question_pack in question_data:
            total_questions = 0
            for round in question_pack.rounds:
                for category in round.categories:
                    total_questions += len(category.questions)

            json_data = question_pack.dump()
            json_data["total_questions"] = total_questions
            questions_json.append(json_data)

        games = database.get_games_for_user(user_id)

        games_json = []
        for game_data in games:
            json_data = game_data.dump()
            json_data["total_questions"] = len(game_data.get_questions_for_round())
            if game_data.stage is not StageType.ENDED:
                json_data["url"] = flask.url_for(f"presenter.{game_data.stage.value}", game_id=game_data.id)

            games_json.append(json_data)

    return make_template_context(
        "dashboard/home.html",
        user_id=user_id,
        user_name=user_name,
        questions=questions_json,
        games=games_json,
    )

@dashboard_page.route("/create_pack", methods=["GET", "POST"])
def create_pack():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_pack")

    user_id, user_name = user_details
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        data = dict(flask.request.form)
        data["created_by"] = user_id
        if data["theme_id"] and data["theme_id"] == "none":
            data["theme_id"] = None

        success, pack_model_or_error = create_and_validate_model(QuestionPack, data, "creating question pack")

        if not success:
            return flask.redirect(flask.url_for(".create_pack", error=pack_model_or_error, _external=True))

        database.create_question_pack(pack_model_or_error)

        data_path = get_question_pack_data_path(pack_model_or_error.id)
        os.mkdir(data_path)

        if "music" in flask.request.files and flask.request.files["music"].filename:
            file = flask.request.files["music"]

            path = os.path.join(data_path, "lobby_music.mp3")
            file.save(path)

        return flask.redirect(flask.url_for(".question_pack", pack_id=pack_model_or_error.id, _external=True))

    return make_template_context(
        "dashboard/create_pack.html",
        user_name=user_name,
        languages=[(lang.value, lang.value.capitalize()) for lang in Language],
    )

@dashboard_page.route("/create_game", methods=["GET", "POST"])
def create_game():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_game")

    user_id, user_name = user_details
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        data = dict(flask.request.form)
        data["created_by"] = user_id
        data["join_code"] = data["title"].lower().replace("'", "").replace(" ", "_") if "title" in data else None

        success, game_model_or_error = create_and_validate_model(Game, data, "creating game")

        if not success:
            return flask.redirect(flask.url_for(".create_game", error=game_model_or_error, _external=True))

        pack_data = database.get_question_packs_for_user(user_id, game_model_or_error.pack_id)
        if not pack_data:
            error = "Error: The selected question pack is invalid."
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True)) 

        # Verify that the join code is unique
        game_model_or_error.join_code = database.get_unique_join_code(game_model_or_error.join_code)

        try:
            database.create_game(game_model_or_error)
        except Exception:
            logger.exception("Error when saving game to database")
            error = "There was an unexpected error when creating the game, please try again later"
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True)) 

        return flask.redirect(flask.url_for("presenter.lobby", game_id=game_model_or_error.id, _external=True))

    questions = database.get_question_packs_for_user(user_id, include_public=True)
    error = flask.request.args.get("error")

    return make_template_context(
        "dashboard/create_game.html",
        user_name=user_name,
        user_id=user_id,
        questions=questions,
        error=error,
    )

@dashboard_page.route("/game/<game_id>/delete", methods=["POST"])
def delete_game(game_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_games_for_user(user_id, game_id) is None:
        return make_json_response("You are not authorized to delete this game", 401)

    try:
        database.delete_game(game_id)
    except Exception:
        logger.exception("Error when deleting game")
        return make_json_response("Unknown error when deleting game", 500)

    return make_json_response("Game was successfully deleted", 200)

@dashboard_page.route("/pack/fetch")
def fetch_resource():
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    url = flask.request.args.get("url")
    if url is None:
        return make_text_response("URL not specified, nothing to fetch", 404)

    # First try to do an 'options' request to just get content-type header
    content_type = None
    try:
        response = requests.options(url)
        status = response.status_code
    except requests.exceptions.RequestException:
        status = 500

    all_valid_types = _VALID_IMAGE_FILETYPES + _VALID_VIDEO_FILETYPES

    if status == 200:
        content_type = response.headers.get("Content-Type")

    if content_type is None or content_type not in all_valid_types:
        # If response is invalid, return error
        response = requests.get(url)
        if response.status_code != 200:
            return make_text_response("Could not fetch resources", response.status_code)

        # If content-type was valid or 'options' request failed, get the full file
        content_type = response.headers.get("Content-Type")
        if content_type not in all_valid_types:
            return make_text_response("Invalid file type to fetch", 400)

    return flask.Response(response.content, 200, headers={"Content-Type": content_type}, mimetype=content_type)

def _save_pack_media_file(pack_id: str, data: Dict[str, Any], file_key: str, files: Dict[str, FileStorage]) -> str | None:
    file_name = data.get(file_key)
    if file_name is None:
        return None

    if (file := files.get(file_name)):
        if file_key == "video":
            allowed_types = ["webm", "mp4"]
        elif file_key == "lobby_music":
            allowed_types = ["mp3", "wav"]
        else:
            allowed_types = ["png", "jpg", "jpeg", "webp"]

        success, error_or_name = validate_file(file, get_question_pack_data_path(pack_id), allowed_types)
        if not success:
            return f"Could not save question image '{file.filename}': {error_or_name}"

        file.save(error_or_name)
        data[file_key] = os.path.basename(error_or_name)

        return None

    # Update filename by removing leading directory path
    data[file_key] = os.path.basename(file_name)

    return None

def _save_pack_files(pack_data:  Dict[str, Any], files: Dict[str, FileStorage]):
    file_keys = ["question_image", "video", "answer_image"]

    for round_data in pack_data["rounds"]:
        for category_data in round_data["categories"]:
            # Upload/update category background image
            error_or_name = _save_pack_media_file(pack_data["id"], category_data, "bg_image", files)
            if error_or_name:
                return error_or_name

            # Upload/update question images
            for question_data in category_data["questions"]:
                for file_key in file_keys:
                    error_or_name = _save_pack_media_file(pack_data["id"], question_data.get("extra", {}), file_key, files)
                    if error_or_name:
                        return error_or_name

    # Save/update lobby music
    error_or_name = _save_pack_media_file(pack_data["id"], pack_data, "lobby_music", files)
    if error_or_name:
        return error_or_name

    return None

def _validate_pack_data(data: Dict[str, Any]) -> str | None:
    success, error_or_model = create_and_validate_model(QuestionPack, data, "saving question pack")

    if not success:
        return error_or_model

    for round_data in data["rounds"]:
        questions_for_round = 0
        for category_data in round_data["categories"]:
            for question_data in category_data["questions"]:
                extra = question_data.get("extra", {})

                # Validate that the multiple choice questions should contain
                # the answer to the question as one of the choices
                round_name = round_data["name"]
                category_name = category_data["name"]
                value = question_data["value"]
                base_error = f"Error at question for {value} points in {round_name}, {category_name}"

                if "choices" in extra:
                    if question_data["answer"] not in extra["choices"]:
                        return f"{base_error}: One of the choices must be equal to the correct answer"

                    for choice in extra["choices"]:
                        if choice == "":
                            return f"{base_error}: Answer choices must not be empty"

                        if len(choice) > 32:
                            return f"{base_error}: Answer choices must be less than 32 characters"

                if ("question_image" in extra or "video" in extra) and "height" not in extra:
                    return f"{base_error}: The height of an image or video must be specified"

                questions_for_round += 1

        if error_or_model.include_finale and round_data["round"] == len(data["rounds"]):
            if len(round_data["categories"]) > 1:
                return f"Error: The finale round must have exactly one category, but has {len(round_data["categories"])}"

            if questions_for_round > 1:
                return f"Error: The finale round must have exactly one question, but has {questions_for_round}"

    return None

@dashboard_page.route("/pack/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_question_packs_for_user(user_id, pack_id) is None:
        return make_json_response("You are not authorized to edit this question package", 401)

    try:
        data: Dict[str, Any] = json.loads(flask.request.form["data"])

        if not data["include_finale"]:
            data["rounds"][-1] = None

        # Add missing entries
        data["created_by"] = user_id
        data["changed_at"] = datetime.now()
        if "language" in data:
            data["language"] = Language(data["language"])

        if "theme_id" in data and data["theme_id"] == "none":
            data["theme_id"] = None

        error = _validate_pack_data(data)
        if error:
            logger.error(error)
            return make_json_response(error, 400)

        error = _save_pack_files(data, flask.request.files)
        if error:
            logger.error(f"Error when saving question media: {error}")
            return make_json_response(error, 400)

        new_ids = database.update_question_pack(data)

    except ValidationError as exc:
        details = ", ".join([get_validation_error_msg(detail) for detail in exc.errors(include_url=False)])
        return make_json_response(f"Error when saving question pack: {details}", 400)

    except Exception:
        logger.exception("Error when saving question pack")
        return make_json_response("Unknown error when saving question pack", 500)

    # Create backup of database for safety
    database.create_backup()

    return make_json_response({"response": "Question pack saved successfully.", "ids": new_ids}, 200)

@dashboard_page.route("/pack/<pack_id>/delete", methods=["POST"])
def delete_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_question_packs_for_user(user_id, pack_id) is None:
        return make_json_response("You are not authorized to delete this question package", 401)

    try:
        database.delete_question_pack(pack_id)
    except Exception:
        logger.exception("Error when deleting question pack")
        return make_json_response("Unknown error when deleting question pack", 500)

    return make_json_response("Question pack was successfully deleted", 200)

@dashboard_page.route("/pack/<pack_id>")
def question_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.question_pack", pack_id=pack_id)

    database: Database = flask.current_app.config["DATABASE"]
    with database:
        user_id, user_name = user_details

        pack_data: QuestionPack | None = database.get_question_packs_for_user(user_id, pack_id)
        if pack_data is None:
            return flask.abort(404)

        pack_json = pack_data.dump(included_relations=[QuestionPack.rounds])
        pack_json["theme_id"] = pack_data.theme_id
        if len(pack_data.rounds) == 1 and not pack_data.include_finale:
            # If finale is not included, provide a placeholder round
            # to make UI handling easier
            pack_json["rounds"].append(
                {
                    "pack_id": pack_data.id,
                    "name": Config.ROUND_NAMES[-1],
                    "round": 2,
                    "categories": [],
                }
            )

        themes_json = [theme.dump() for theme in database.get_themes_for_user(user_id, include_public=True)]

        base_entries = {k: v for k, v in pack_json.items() if not isinstance(v, list)}

    return render_locale_template(
        "dashboard/question_pack.html",
        pack_data.language,
        user_name=user_name,
        languages=[(lang.value, lang.value.capitalize()) for lang in Language],
        themes=themes_json,
        base_entries=base_entries,
        **pack_json,
    )

