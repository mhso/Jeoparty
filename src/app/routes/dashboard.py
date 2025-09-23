import json
import os
from typing import Any, Dict

import flask

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response
from mhooge_flask.logging import logger

from api.database import Database
from api.config import get_data_path_for_question_pack
from api.orm.models import *
from api.enums import StageType
from app.routes.shared import (
    redirect_to_login,
    validate_param,
    validate_file,
    render_locale_template,
    VALID_NAME_CHARACTERS
)

dashboard_page = flask.Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_page.route("/")
def home():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.home")

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    with database:
        question_data = database.get_questions_for_user(user_id)
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

def _validate_create_pack_params(params: Dict[str, Any], user_id: str):
    name, error = validate_param(params, "name", str, 1, 64)
    if error:
        return error

    for c in name:
        if c.strip() not in VALID_NAME_CHARACTERS:
            return f"Invalid character in question pack name: {c}"

    public = "public" in params
    finale = "finale" in params

    if "language" not in params:
        language = Language.ENGLISH
    else:
        try:
            language = getattr(Language, params["language"])
        except AttributeError:
            return f"Unsupported language: '{params['language']}'"

    return QuestionPack(
        name=name,
        public=public,
        include_finale=finale,
        language=language,
        created_by=user_id,
    )

@dashboard_page.route("/create_pack", methods=["GET", "POST"])
def create_pack():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_pack")

    user_id, user_name = user_details
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        pack_model_or_error = _validate_create_pack_params(flask.request.form, user_id)

        if not isinstance(pack_model_or_error, QuestionPack) and pack_model_or_error is not None:
            return flask.redirect(flask.url_for(".question_pack", error=pack_model_or_error, _external=True))

        database.create_question_pack(pack_model_or_error)

        data_path = get_data_path_for_question_pack(pack_model_or_error.id)
        os.mkdir(data_path)

        if "music" in flask.request.files:
            file = flask.request.files["music"]

            path = os.path.join(data_path, "lobby_music.mp3")
            file.save(path)

        return flask.redirect(flask.url_for(".question_pack", pack_id=pack_model_or_error.id, _external=True))

    return make_template_context(
        "dashboard/create_pack.html",
        user_name=user_name,
        languages=[(lang.name, lang.value.capitalize()) for lang in Language],
    )

def _validate_create_game_params(params: Dict[str, Any], user_id: str) -> Game | str:
    title, error = validate_param(params, "title", str, 3, 64)
    if error:
        return error

    for c in title:
        if c.strip() not in VALID_NAME_CHARACTERS:
            return f"Invalid character in game title: {c}"

    if "password" in params and params["password"] != "":
        password, error = validate_param(params, "password", str, 3, 128)
        if error:
            return error
    else:
        password = None

    rounds, error = validate_param(params, "rounds", int, 1, 9)
    if error:
        return error

    contestants, error = validate_param(params, "contestants", int, 1, 9)
    if error:
        return error

    pack_id, error = validate_param(params, "pack_id", str, 36, 36)
    if error:
        return error

    if pack_id == "missing":
        return "Choose a valid question pack"

    daily_doubles = "daily_doubles" in params
    power_ups = "power_ups" in params

    join_code = title.lower().replace(" ", "_").replace("'", "")

    return Game(
        pack_id=pack_id,
        title=title,
        join_code=join_code,
        regular_rounds=rounds,
        max_contestants=contestants,
        use_daily_doubles=daily_doubles,
        use_powerups=power_ups,
        password=password,
        created_by=user_id,
    )

@dashboard_page.route("/create_game", methods=["GET", "POST"])
def create_game():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_game")

    user_id, user_name = user_details
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        game_model_or_error = _validate_create_game_params(flask.request.form, user_id)

        if not isinstance(game_model_or_error, Game) and game_model_or_error is not None:
            return flask.redirect(flask.url_for(".create_game", error=game_model_or_error, _external=True))

        # Verify that the join code is unique
        game_model_or_error.join_code = database.get_unique_join_code(game_model_or_error.join_code)

        try:
            database.create_game(game_model_or_error)
        except Exception:
            logger.exception("Error when saving game to database")
            error = "There was an unexpected error when creating the game, please try again later"
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True)) 

        return flask.redirect(flask.url_for("presenter.lobby", game_id=game_model_or_error.id, _external=True))

    questions = database.get_questions_for_user(user_id, include_public=True)
    error = flask.request.args.get("error")

    return make_template_context(
        "dashboard/create_game.html",
        user_name=user_name,
        user_id=user_id,
        questions=questions,
        error=error,
    )

def _save_pack_file(pack_id, file, allowed_types):
    success, error_or_name = validate_file(file, allowed_types)
    if not success:
        return False, f"Could not save question image '{file.filename}': {error_or_name}"

    path = os.path.join(get_data_path_for_question_pack(pack_id), error_or_name)
    file.save(path)

    return True, error_or_name

def _save_pack_files(pack_data, files):
    file_keys = ["question_image", "video", "answer_image"]

    for round_data in pack_data["rounds"]:
        for category_data in round_data["categories"]:
            for question_data in category_data["questions"]:
                for file_key in file_keys:
                    file_name = question_data["extra"].get(file_key)
                    if file_name is not None and file_name in files:
                        allowed_types = ["webm", "mp4"] if file_key == "video" else ["png", "jpg", "jpeg", "webp"]
                        success, error_or_name = _save_pack_file(pack_data["id"], files[file_name], allowed_types)
                        if not success:
                            return f"Could not save question image '{file_name}': {error_or_name}"

                        question_data["extra"][file_key] = error_or_name

    return None

@dashboard_page.route("/pack/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_questions_for_user(user_id, pack_id) is None:
        return make_text_response("You are not authorized to edit this question package", 401)

    try:
        data: Dict[str, Any] = json.loads(flask.request.form["data"])

        print("Data:", data)
        print("Files:", list(flask.request.files.keys()))

        error = _save_pack_files(data, flask.request.files)
        if error:
            logger.error(f"Error when saving question media: {error}")
            return make_text_response(error, 400)

        if not data["include_finale"]:
            data["rounds"][-1] = None

        # Add missing entries
        data["created_by"] = user_id
        data["changed_at"] = datetime.now()
        if "language" in data:
            data["language"] = getattr(Language, data["language"])

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

        pack_data: QuestionPack | None = database.get_questions_for_user(user_id, pack_id)
        if pack_data is None:
            return flask.abort(404)

        pack_json = pack_data.dump(include_relations=False)
        base_entries = dict(pack_json.items())
        pack_json["rounds"] = [
            round_data.dump_questions_nested(
                remap_keys=False,
                round=["pack"],
                category=["round"],
                question=["category", "game_questions"],
            )
            for round_data in pack_data.rounds
        ]

    return render_locale_template(
        "dashboard/question_pack.html",
        pack_data.language,
        user_name=user_name,
        languages=[(lang.name, lang.value.capitalize()) for lang in Language],
        base_entries=base_entries,
        **pack_json,
    )

@dashboard_page.route("/pack/<pack_id>/question/<question_id>")
def question_view(pack_id: str, question_id: str):
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.question_view", pack_id=pack_id, question_id=question_id)

    database: Database = flask.current_app.config["DATABASE"]
    with database:
        pack = database.get_questions_for_user(user_details[0], pack_id)

        if pack is None:
            return flask.abort(404)

        question = None
        for pack_question in pack.get_all_questions():
            if pack_question.id == question_id:
                question = pack_question
                break

        if question is None:
            return flask.abort(404)

        question_json = question.dump(id="question_id")

    return render_locale_template(
        "question_view.html",
        pack.language,
        editable=True,
        stage="QUESTION",
        **question_json,
    )
