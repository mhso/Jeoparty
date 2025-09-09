import os
from typing import Any, Dict

import flask

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response
from mhooge_flask.logging import logger

from api.database import Database
from api.orm.models import *
from api.enums import StageType
from app.routes.shared import redirect_to_login, validate_param, get_data_path_for_question_pack

_UPPERCASE = [chr(i) for i in range(65, 91)]
_LOWERCASE = [chr(x) for x in range(97, 123)]
_NUMBERS = [str(i) for i in range(0, 10)]
_EXTRA = ["_", "-", "'", ""]
VALID_CHARS = set(_UPPERCASE + _LOWERCASE + _NUMBERS + _EXTRA)

dashboard_page = flask.Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_page.route("/")
def home():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.home")

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    question_data = database.get_questions_for_user(user_id)
    questions_json = []
    for question_pack in question_data:
        total_questions = 0
        for round in question_pack.rounds:
            for category in round.categories:
                total_questions += len(category.questions)

        question_pack.json["total_questions"] = total_questions
        questions_json.append(question_pack.json)

    games = database.get_games_for_user(user_id)

    games_json = []
    for game in games:
        if game.stage is not StageType.ENDED:
            game.json["url"] = flask.url_for(f"presenter.{game.stage.value}", game_id=game.id)
            games_json.append(game.json)

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
        if c.strip() not in VALID_CHARS:
            return f"Invalid character in question pack name: {c}"

    public = "public" in params
    finale = "finale" in params

    if "music" in flask.request.files:
        file = flask.request.files["music"]
        if not file.filename:
            return "No lobby music selected"

        file_split = file.filename.split(".")
        if len(file_split) != 2 or file_split[1] != "mp3":
            return "Invalid lobby music file type, must be .mp3"

    return QuestionPack(
        name=name,
        public=public,
        include_finale=finale,
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
            return flask.redirect(flask.url_for(".create_game", error=pack_model_or_error, _external=True))

        database.create_question_pack(pack_model_or_error)

        data_path = get_data_path_for_question_pack(pack_model_or_error.id)
        os.mkdir(data_path)

        if "music" in flask.request.form:
            file = flask.request.files["music"]

            path = os.path.join(data_path, "lobby_music.mp3")
            file.save(path)

        return flask.redirect(flask.url_for(".questions_view", pack_id=pack_model_or_error.id, _external=True))

    return make_template_context("dashboard/create_pack.html", user_name=user_name)

def _validate_create_game_params(params: Dict[str, Any], user_id: str) -> Game | str:
    title, error = validate_param(params, "title", str, 3, 64)
    if error:
        return error

    for c in title:
        if c.strip() not in VALID_CHARS:
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

@dashboard_page.route("/pack/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_questions_for_user(user_id, pack_id) is None:
        return make_text_response("You are not authorized to edit this question package", 401)

    data: Dict[str, Any] = flask.request.json

    if not data["include_finale"]:
        data["rounds"][-1] = None

    # Add missing entries
    data["created_by"] = user_id
    data["changed_at"] = datetime.now()

    database.update_question_pack(data)

    return make_text_response("Question pack saved succesfully.", 200)

@dashboard_page.route("/pack/<pack_id>")
def questions_view(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.questions_view", pack_id=pack_id)

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    question_data: QuestionPack | None = database.get_questions_for_user(user_id, pack_id)
    if question_data is None:
        return flask.abort(404)

    return make_template_context(
        "dashboard/question_pack.html",
        user_name=user_name,
        **question_data.json,
    )
