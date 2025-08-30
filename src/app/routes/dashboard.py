from typing import Any, Dict
from uuid import uuid4

import flask

from mhooge_flask.auth import get_user_details
from mhooge_flask.routing import make_template_context, make_text_response

from api.database import Database
from app.routes.util import redirect_to_login, validate_param

dashboard_page = flask.Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_page.route("/")
def home():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.home")

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    questions = database.get_questions_for_user(user_id)
    games = database.get_games_for_user(user_id)
    for game in games:
        if not game["ended_at"]:
            params = {}
            if game["stage"] in ("selection", "question"):
                params["jeopardy_round"] = game["round"]
            if game["stage"] == "question":
                params["category"] = game["category"]
                params["tier"] = game["tier"]

            game["url"] = flask.url_for(f"presenter.{game["stage"]}", **params)

    return make_template_context(
        "dashboard/home.html",
        user_id=user_id,
        user_name=user_name,
        questions=questions,
        games=games,
    )

def _validate_create_pack_params(params: Dict[str, Any]):
    name, error = validate_param(params, "name", str, 1, 64)
    if error:
        return error

    public = "public" in params

    return name, public

@dashboard_page.route("/create_pack", methods=["GET", "POST"])
def create_pack():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_pack")

    user_id, user_name = user_details
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        validate_result = _validate_create_pack_params(flask.request.form)

        if not isinstance(validate_result, tuple) and validate_result is not None:
            return flask.redirect(flask.url_for(".create_game", error=validate_result, _external=True))

        name, public = validate_result

        pack_id = uuid4().hex
        database.create_question_pack(pack_id, user_id, name, public)

        return flask.redirect(flask.url_for(".questions_view", pack_id=pack_id, _external=True))

    return make_template_context("dashboard/create_pack.html", user_name=user_name)

@dashboard_page.route("/<pack_id>/save")
def save_pack(pack_id: str):


    return make_text_response("Question pack saved succesfully", 200)

@dashboard_page.route("/<pack_id>")
def questions_view(pack_id: str):
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.questions_view", pack_id=pack_id)

    database: Database = flask.current_app.config["DATABASE"]
    user_id, user_name = user_details

    question_data = database.get_questions_for_user(user_id, pack_id)

    return make_template_context(
        "dashboard/question_pack.html",
        user_name=user_name,
        pack_id=pack_id,
        **question_data,
    )

def _validate_create_game_params(params: Dict[str, Any]):
    title, error = validate_param(params, "title", str, 1, 64)
    if error:
        return error

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

    return title, rounds, contestants, pack_id

@dashboard_page.route("/create_game", methods=["GET", "POST"])
def create_game():
    user_details = get_user_details()
    if user_details is None:
        return redirect_to_login("dashboard.create_game")

    user_id = user_details[0]
    database: Database = flask.current_app.config["DATABASE"]

    if flask.request.method == "POST":
        validate_result = _validate_create_game_params(flask.request.form)

        if not isinstance(validate_result, tuple) and validate_result is not None:
            return flask.redirect(flask.url_for(".create_game", error=validate_result, _external=True))

        title, rounds, contestants, pack_id = validate_result

        if database.get_questions_for_user(user_id, pack_id, True) == []:
            error = "The given question pack does not exist or you do not have access to it"
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True))

        game_id = uuid4().hex
        success = database.create_game(game_id, pack_id, user_id, rounds, contestants, title)
        if not success:
            error = "There was an unexpected error when creating the game, please try again later"
            return flask.redirect(flask.url_for(".create_game", error=error, _external=True)) 

        return flask.redirect(flask.url_for("presenter.lobby", game_id=game_id, _external=True))

    questions = database.get_questions_for_user(user_id, include_public=True)
    error = flask.request.args.get("error")

    return make_template_context(
        "dashboard/create_game.html",
        user_id=user_id,
        questions=questions,
        error=error,
    )
