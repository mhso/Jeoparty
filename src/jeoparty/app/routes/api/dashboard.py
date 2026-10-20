import json
import os
from time import sleep
from typing import Any, Dict
from pydantic import ValidationError
import requests

import flask
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_text_response, make_json_response
from mhooge_flask.logging import logger

from jeoparty.api.database import Database, get_violating_key
from jeoparty.api.config import Config, get_question_pack_data_path
from jeoparty.api.orm.models import *
from jeoparty.api.enums import StageType
from jeoparty.app.routes.shared import (
    validate_file,
    get_validation_error_msg,
    create_and_validate_model,
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

_UNAUTHORIZED_MSG = "You are authorized to access this. Please log in first."

dashboard_page = flask.Blueprint("dashboard_api", __name__, template_folder="templates")

@dashboard_page.route("/packs", methods=["GET", "POST"])
def packs():
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        if flask.request.method == "POST":
            # POST request when creating a new question pack
            data = dict(flask.request.form)
            data["created_by"] = user_details[0]
            if data.get("theme_id", "") == "none":
                data["theme_id"] = None

            action = "creating question pack"
            success, pack_model_or_error = create_and_validate_model(QuestionPack, data, action)

            if not success:
                return make_json_response(pack_model_or_error, 400)

            lobby_music_filename = "lobby_music.mp3"
            has_lobby_music = "music" in flask.request.files and flask.request.files["music"].filename
            if has_lobby_music:
                file = flask.request.files["music"]
                allowed_types = ["mp3", "wav"]
                success, error_or_name = validate_file(file, allowed_types, default_name=lobby_music_filename)
                if not success:
                    error_msg = f"Could not validate question file '{file.filename}': {error_or_name}"
                    return make_json_response(error_msg, 400)

                pack_model_or_error.lobby_music = error_or_name

            # Save the question pack to the database
            try:
                pack_model = database.create_question_pack(pack_model_or_error)
            except IntegrityError as exc:
                input_err = get_violating_key(exc)
                if input_err is None:
                    raise

                error_msg = f"Error when {action}: '{input_err[0]}' - Input does not refer to a valid theme" 
                return make_json_response(error_msg, 400)
            except Exception:
                logger.exception("Error when saving question pack to database")
                error_msg = "There was an unexpected error when creating the question pack, please try again later"
                return make_json_response(error_msg, 500)

            data_path = get_question_pack_data_path(pack_model_or_error.id)
            os.mkdir(data_path)

            if has_lobby_music:
                path = os.path.join(data_path, lobby_music_filename)
                file.save(path)

            return make_json_response(pack_model.dump(), 200)

        # Otherwise, GET request when fetching all question packs
        packs_json = []
        question_data = database.get_question_packs_for_user(user_details[0])
        for question_pack in question_data:
            total_questions = 0
            for round in question_pack.rounds:
                for category in round.categories:
                    total_questions += len(category.questions)

            json_data = question_pack.dump()
            json_data["total_questions"] = total_questions
            packs_json.append(json_data)

    return make_json_response(packs_json, 200)

@dashboard_page.route("/games", methods=["GET", "POST"])
def games():
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        if flask.request.method == "POST":
            data = dict(flask.request.form)
            data["created_by"] = user_details[0]
            data["join_code"] = data["title"].lower().replace("'", "").replace(" ", "_") if "title" in data else None

            success, game_model_or_error = create_and_validate_model(Game, data, "creating game")
        
            if not success:
                return make_json_response(game_model_or_error, 400)
        
            # Check if question pack exists
            pack_data = database.get_question_packs_for_user(user_details[0], game_model_or_error.pack_id)
            if not pack_data:
                error_msg = "Error when creating game: The selected question pack is invalid."
                return make_json_response(error_msg, 400)
        
            # Check if question pack supports the given rounds
            pack_rounds = len(pack_data.rounds) - 1 if pack_data.include_finale else len(pack_data.rounds)
            if game_model_or_error.regular_rounds > pack_rounds:
                round_plural = "round" if pack_rounds == 1 else "rounds"
                error_msg = f"Error when creating game: The question pack only supports {pack_rounds} regular {round_plural}."
                return make_json_response(error_msg, 400)
        
            # Verify that the join code is unique
            game_model_or_error.join_code = database.get_unique_join_code(game_model_or_error.join_code)
        
            try:
                game_model = database.create_game(game_model_or_error)
            except Exception:
                logger.exception("Error when saving game to database")
                error_msg = "There was an unexpected error when creating the game, please try again later"
                return make_json_response(error_msg, 500)
        
            return make_json_response(game_model.dump(), 200)

        games_json = []
        games = database.get_games_for_user(user_details[0])
    
        for game_data in games:
            json_data = game_data.dump(included_relations=[Game.pack])
            json_data["total_questions"] = len(game_data.get_questions_for_round())
            if game_data.stage is not StageType.ENDED:
                if game_data.stage is StageType.FINALE_WAGER:
                    stage = "selection"
                elif game_data.stage is StageType.FINALE_QUESTION:
                    stage = "question"
                elif game_data.stage is StageType.FINALE_RESULT:
                    stage = "finale"
                else:
                    stage = game_data.stage.value

                json_data["resume_path"] = f"/jeoparty/presenter/{game_data.id}/{stage}"

            games_json.append(json_data)

    return make_json_response(games_json, 200)


@dashboard_page.route("/games/<game_id>", methods=["DELETE"])
def delete_game(game_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        if database.get_games_for_user( user_details[0], game_id) is None:
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

    if 200 <= status < 300:
        content_type = response.headers.get("Content-Type")

    if content_type is None or content_type not in all_valid_types:
        # If content-type was valid or 'options' request failed, get the full file
        sleep(0.5)

        response = requests.get(url)

        if response.status_code != 200:
            # If response is invalid, return error
            return make_text_response("Could not fetch resources", response.status_code)

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

        success, error_or_name = validate_file(file, allowed_types, get_question_pack_data_path(pack_id))
        if not success:
            return f"Could not validate question file '{file.filename}': {error_or_name}"

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

def _get_error_data(
    message: str,
    round_id: int | None = None,
    category_id: int | None = None,
    question_id: int | None = None,
    field: str | None = None,
    index: int | None = None,
):
    data: Dict[str, str | int] = {"response": message}

    for key, val in [
        ("round_id", round_id),
        ("category_id", category_id),
        ("question_id", question_id),
        ("field", field),
        ("index", index),
    ]:
        if val:
            data[key] = val

    return data

def _validate_pack_data(data: Dict[str, Any]) -> Dict[str, str | int] | None:
    success, error_or_model = create_and_validate_model(QuestionPack, data, "saving question pack")

    if not success:
        return _get_error_data(error_or_model)

    for round_data in data["rounds"]:
        questions_for_round = 0
        for category_data in round_data["categories"]:
            for question_data in category_data["questions"]:
                extra = question_data.get("extra", {})

                # Validate that the multiple choice questions should contain
                # the answer to the question as one of the choices
                if "choices" in extra:
                    if question_data["answer"] not in extra["choices"]:
                        return _get_error_data(
                            "One of the choices must be equal to the correct answer",
                            round_data["id"],
                            category_data["id"],
                            question_data["id"],
                            "choices",
                        )

                    if len(extra["choices"]) > Config.MAX_ANSWER_CHOICES:
                        return _get_error_data(
                            f"Amount of answer choices must not be greater than {Config.MAX_ANSWER_CHOICES}",
                            round_data["id"],
                            category_data["id"],
                            question_data["id"],
                            "choices",
                        )

                    for index, choice in enumerate(extra["choices"], start=1):
                        if choice == "":
                            return _get_error_data(
                                "Answer choice must not be empty",
                                round_data["id"],
                                category_data["id"],
                                question_data["id"],
                                "choices",
                                index,
                            )

                        if len(choice) > 32:
                            return _get_error_data(
                                "Answer choice must be less than 32 characters",
                                round_data["id"],
                                category_data["id"],
                                question_data["id"],
                                "choices",
                                index,
                            )

                if ("question_image" in extra or "video" in extra) and "height" not in extra:
                    return _get_error_data(
                        "The height of an image or video must be specified",
                        round_data["id"],
                        category_data["id"],
                        question_data["id"],
                        "media",
                    )

                questions_for_round += 1

        if error_or_model.include_finale and round_data["round"] == len(data["rounds"]):
            if len(round_data["categories"]) > 1:
                return _get_error_data(
                    f"The finale round must have exactly one category, but has {len(round_data["categories"])}",
                    round_data["id"],
                )

            if questions_for_round > 1:
                return _get_error_data(
                    f"The finale round must have exactly one question, but has {questions_for_round}",
                    round_data["id"],
                )

    return None

@dashboard_page.route("/pack/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    with database:
        if database.get_question_packs_for_user(user_id, pack_id) is None:
            return make_json_response(_get_error_data("You are not authorized to edit this question package"), 401)

        try:
            data: Dict[str, Any] = json.loads(flask.request.form["data"])

            if not data["include_finale"]:
                data["rounds"] = [round_data for round_data in data["rounds"] if round_data["round"] <= len(data["rounds"])]

            # Add missing entries
            data["created_by"] = user_id
            data["changed_at"] = datetime.now()
            if "language" in data:
                data["language"] = Language(data["language"])

            if "theme_id" in data and data["theme_id"] == "none":
                data["theme_id"] = None

            error = _validate_pack_data(data)
            if error:
                logger.bind(**error).error(error["response"])
                return make_json_response(error, 400)

            error = _save_pack_files(data, flask.request.files)
            if error:
                logger.bind(**error).error(f"Error when saving question media: {error['response']}")
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

@dashboard_page.route("/pack/<pack_id>/cheatsheet")
def cheatsheet(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        pack_data: QuestionPack | None = database.get_question_packs_for_user(user_details[0], pack_id)
        if pack_data is None:
            return make_json_response("You are not auhorized to view this cheatsheet.", 401)

        pack_json = pack_data.dump(included_relations=QuestionPack.rounds)

    return make_json_response(pack_json, 200)

@dashboard_page.route("/packs/<pack_id>", methods=["GET", "DELETE"])
def question_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_json_response(_UNAUTHORIZED_MSG, 401)

    database: Database = flask.current_app.config["DATABASE"]
    
    with database:
        if flask.request.method == "DELETE":
            # DELETE request when deleting a question pack
            if database.get_question_packs_for_user(user_details[0], pack_id) is None:
                return make_json_response("You are not authorized to delete this question package", 401)

            try:
                database.delete_question_pack(pack_id)
            except Exception:
                logger.exception("Error when deleting question pack")
                return make_json_response("Unknown error when deleting question pack", 500)

            return make_json_response("Question pack was successfully deleted", 200)

        pack_model: QuestionPack | None = database.get_question_packs_for_user(user_details[0], pack_id)
        if pack_model is None:
            return flask.abort(404)

        pack_json = pack_model.dump(included_relations=[QuestionPack.rounds])
        pack_json["theme_id"] = pack_model.theme_id

        if len(pack_model.rounds) == 1 and not pack_model.include_finale:
            # If finale is not included, provide a placeholder round
            # to make UI handling easier
            pack_json["rounds"].append(
                {
                    "pack_id": pack_model.id,
                    "name": Config.DEFAULT_ROUND_NAMES[-1],
                    "round": 2,
                    "categories": [],
                }
            )

    return make_json_response(pack_json, 200)

@dashboard_page.route("/themes")
def themes():
    return "Not implemented yet", 200

@dashboard_page.route("/ping")
def ping():
    return "OK"
