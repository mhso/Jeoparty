import json
import os
from typing import Any, Dict
import requests

import flask

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response
from mhooge_flask.logging import logger

from jeoparty.api.database import Database
from jeoparty.api.config import get_question_pack_data_path
from jeoparty.api.orm.models import *
from jeoparty.api.enums import StageType
from jeoparty.app.routes.shared import (
    redirect_to_login,
    validate_file,
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
        success, pack_model_or_error = create_and_validate_model(QuestionPack, data, "creating question pack")

        if not success:
            return flask.redirect(flask.url_for(".create_pack", error=pack_model_or_error, _external=True))

        database.create_question_pack(pack_model_or_error)

        data_path = get_question_pack_data_path(pack_model_or_error.id)
        os.mkdir(data_path)

        if "music" in flask.request.files:
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

@dashboard_page.route("/pack/fetch")
def fetch_resource():
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    url = flask.request.args.get("url")
    if url is None:
        return make_text_response("URL not specified, nothing to fetch", 404)

    response = requests.options(url)
    content_type = response.headers.get("Content-Type")

    if content_type not in _VALID_IMAGE_FILETYPES and content_type not in _VALID_VIDEO_FILETYPES:
        return make_text_response("Invalid file type to fetch", 400)

    response = requests.get(url)
    if response.status_code != 200:
        return make_text_response("Could not fetch resources", response.status_code)

    with open("test.png", "wb") as fp:
        fp.write(response.content)

    return flask.Response(response.content, 200, headers={"Content-Type": content_type}, mimetype=content_type)

def _save_pack_file(pack_id, file, allowed_types):
    success, error_or_name = validate_file(file, allowed_types)
    print(error_or_name)
    if not success:
        return False, f"Could not save question image '{file.filename}': {error_or_name}"

    path = os.path.join(get_question_pack_data_path(pack_id), error_or_name)
    file.save(path)

    return True, error_or_name

def _save_pack_files(pack_data, files):
    file_keys = ["question_image", "video", "answer_image"]

    for round_data in pack_data["rounds"]:
        for category_data in round_data["categories"]:
            for question_data in category_data["questions"]:
                for file_key in file_keys:
                    file_name = question_data["extra"].get(file_key)
                    if file_name is None:
                        continue

                    if file_name in files:
                        allowed_types = ["webm", "mp4"] if file_key == "video" else ["png", "jpg", "jpeg", "webp"]
                        success, error_or_name = _save_pack_file(pack_data["id"], files[file_name], allowed_types)
                        if not success:
                            return error_or_name

                        question_data["extra"][file_key] = error_or_name
                    else:
                        question_data["extra"][file_key] = os.path.basename(file_name)

    return None

def _validate_pack_data(data: Dict[str, Any]) -> str | None:
    success, error_or_model = create_and_validate_model(QuestionPack, data, "saving question pack")

    if not success:
        return error_or_model
    
    for round_data in data["rounds"]:
        for category_data in round_data["categories"]:
            for question_data in category_data["questions"]:
                extra = question_data.get("extra", {})

                # Validate that the multiple choice questions should contain
                # the answer to the question as one of the choices
                if "choices" in extra and question_data["answer"] not in extra["choices"]:
                    return "Error when saving question pack: One of the choices must be equal to the correct answer"

                if ("question_image" in extra or "video" in extra) and "height" not in extra:
                    return "Error when saving question pack: The height of an image or video must be specified"

    return None

@dashboard_page.route("/pack/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_question_packs_for_user(user_id, pack_id) is None:
        return make_text_response("You are not authorized to edit this question package", 401)

    try:
        data: Dict[str, Any] = json.loads(flask.request.form["data"])
        print(data)
        print(list(flask.request.files.keys()))

        if not data["include_finale"]:
            data["rounds"][-1] = None

        # Add missing entries
        data["created_by"] = user_id
        data["changed_at"] = datetime.now()
        if "language" in data:
            data["language"] = Language(data["language"])

        error = _validate_pack_data(data)
        if error:
            logger.error(error)
            return make_text_response(error, 400)

        error = _save_pack_files(data, flask.request.files)
        if error:
            logger.error(f"Error when saving question media: {error}")
            return make_text_response(error, 400)

        database.update_question_pack(data)
    except Exception:
        logger.exception("Error when saving question pack")
        return make_text_response("Unknown error when saving question pack", 500)

    return make_text_response("Question pack saved succesfully.", 200)

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
        base_entries = {k: v for k, v in pack_json.items() if not isinstance(v, list)}

    return render_locale_template(
        "dashboard/question_pack.html",
        pack_data.language,
        user_name=user_name,
        languages=[(lang.value, lang.value.capitalize()) for lang in Language],
        base_entries=base_entries,
        **pack_json,
    )
