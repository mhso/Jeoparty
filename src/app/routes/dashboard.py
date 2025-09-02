import os
from typing import Any, Dict

import flask

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response

from api.database import Database
from api.orm.models import *
from api.enums import Stage
from app.routes.shared import redirect_to_login, validate_param, get_data_path_for_question_pack

dashboard_page = flask.Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_page.route("/")
def home():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.home")

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    questions = [question.json for question in database.get_questions_for_user(user_id)]
    games = database.get_games_for_user(user_id)
    games_json = []
    for game in games:
        if game.stage is not Stage.ENDED:
            game.json["url"] = flask.url_for(f"presenter.{game.stage.value}", game_id=game.id)
            games_json.append(game.json)

    return make_template_context(
        "dashboard/home.html",
        user_id=user_id,
        user_name=user_name,
        questions=questions,
        games=games_json,
    )

def _validate_create_pack_params(params: Dict[str, Any], user_id: str):
    name, error = validate_param(params, "name", str, 1, 64)
    if error:
        return error

    public = "public" in params
    finale = "finale" in params

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

        return flask.redirect(flask.url_for(".questions_view", pack_id=pack_model_or_error.id, _external=True))

    return make_template_context("dashboard/create_pack.html", user_name=user_name)

def _validate_create_game_params(params: Dict[str, Any], user_id: str) -> Game | str:
    title, error = validate_param(params, "title", str, 1, 64)
    if error:
        return error

    if "password" in params:
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

    pack_id, error = validate_param(params, "pack_id", str, 1, 32)
    if error:
        return error

    if pack_id == "missing":
        return "Choose a valid question pack"

    daily_doubles = "daily_doubles" in params
    power_ups = "power_ups" in params

    if "music" in flask.request.files:
        file = flask.request.files["music"]
        if not file.filename:
            return "No lobby music selected"

        file_split = file.filename.split(".")
        if not len(file_split) != 2 or file_split[1] != "mp3":
            return "Invalid lobby music file type, must be .mp3"

    return Game(
        pack_id=pack_id,
        title=title,
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

    user_id = user_details[0]
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        game_model_or_error = _validate_create_game_params(flask.request.form, user_id)

        if not isinstance(game_model_or_error, Game) and game_model_or_error is not None:
            return flask.redirect(flask.url_for(".create_game", error=game_model_or_error, _external=True))

        success = database.create_game(game_model_or_error)
        if not success:
            error = "There was an unexpected error when creating the game, please try again later"
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True)) 

        data_path = get_data_path_for_question_pack(game_model_or_error.pack_id)
        os.mkdir(data_path)

        if "music" in flask.request.form:
            file = flask.request.files["music"]

            path = os.path.join(data_path, "lobby_music.mp3")
            file.save(path)

        return flask.redirect(flask.url_for("presenter.lobby", game_id=game_model_or_error.id, _external=True))

    questions = database.get_questions_for_user(user_id, include_public=True)
    error = flask.request.args.get("error")

    return make_template_context(
        "dashboard/create_game.html",
        user_id=user_id,
        questions=questions,
        error=error,
    )

@dashboard_page.route("/<pack_id>/save", methods=["POST"])
def save_pack(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return make_text_response("You are not logged in!", 401)

    database: Database = flask.current_app.config["DATABASE"]
    user_id = user_details[0]

    if database.get_questions_for_user(user_id, pack_id) is None:
        return make_text_response("You are not authorized to edit this question package", 401)

    data: Dict[str, Any] = flask.request.json
    pack_model = QuestionPack(**data)

    database.save_question_pack(pack_model)

    return make_text_response("Question pack saved succesfully.", 200)

@dashboard_page.route("/<pack_id>")
def questions_view(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.questions_view", pack_id=pack_id)

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    question_data: QuestionPack = database.get_questions_for_user(user_id, pack_id)

    return make_template_context(
        "dashboard/question_pack.html",
        user_name=user_name,
        pack_id=pack_id,
        **question_data.json,
    )
