import os
from typing import Any, Dict

import flask

from api.database import Database
from api.orm.models import Contestant, GameContestant
from app.routes.shared import validate_param, render_locale_template
from api.config import get_avatar_path

contestant_page = flask.Blueprint("contestant", __name__, template_folder="templates")

_VALID_AVATAR_FILETYPES = set(["jpg", "jpeg", "png", "webp"])
_COOKIE_ID = "jeoparty_contestant_id"

def _save_user_id_to_cookie(user_id: str):
    max_age = 60 * 60 * 24 * 365 # 1 year
    return _COOKIE_ID, user_id, max_age

def _get_user_id_from_cookie(cookies) -> str:
    return str(cookies.get(_COOKIE_ID))

def _validate_join_params(params: Dict[str, Any]) -> Contestant | str:
    name, error = validate_param(params, "name", str, 2, 16)
    if error:
        return error

    color, error = validate_param(params, "color", str)
    if error:
        return error

    if "join_code" not in params:
        return "Failed to join: Lobby ID is missing"

    if "default_avatar" not in flask.request.form and "avatar" in flask.request.files and flask.request.files["avatar"].filename:
        file = flask.request.files["avatar"]
        file_split = file.filename.split(".")
        if len(file_split) != 2 or file_split[1] not in _VALID_AVATAR_FILETYPES:
            return "Invalid avatar file type, must be .jpg, .png, or .webp"

    return Contestant(name=name, color=color)

def _get_random_bg_image(index):
    return None # TODO: Make this sometime

def _save_contestant_avatar(file, user_id):
    file_split = file.filename.split(".")
    filename = f"{user_id}.{file_split[1]}"
    path = os.path.join(get_avatar_path(), filename)

    file.save(path)

    return filename

@contestant_page.route("/join", methods=["POST"])
def join_lobby():
    database: Database = flask.current_app.config["DATABASE"]

    contestant_model_or_error = _validate_join_params(flask.request.form)
    join_code = flask.request.form.get("join_code")

    if not isinstance(contestant_model_or_error, Contestant) and contestant_model_or_error is not None:
        if join_code is None:
            return flask.abort(400)

        return flask.redirect(flask.url_for(".lobby", join_code=join_code, error=contestant_model_or_error, _external=True))

    user_id = flask.request.form.get("user_id")

    with database:
        game_data = database.get_game_from_code(join_code)
        if game_data is None:
            return flask.redirect(
                flask.url_for(".lobby", join_code=join_code, error="Failed to join: Game does not exist")
            )

        index = len(game_data.game_contestants)
        if index == game_data.max_contestants:
            return flask.redirect(
                flask.url_for(".lobby", join_code=join_code, error="Failed to join: Lobby is already full")
            )

        # Try to get existitng user
        existing_model = None if user_id is None else database.get_contestant_from_id(user_id)

        user_already_joined = False
        if existing_model is not None:
            contestant_model_or_error.id = existing_model.id
            contestant_model_or_error.avatar = existing_model.avatar
            contestant_model_or_error.bg_image = existing_model.bg_image
            contestant_model_or_error.buzz_sound = existing_model.buzz_sound

            for contestant in game_data.game_contestants:
                if contestant.contestant_id == user_id:
                    user_already_joined = True
                    break

        # Get or set background image
        contestant_model_or_error.bg_image = flask.request.form.get("bg_image")

        if contestant_model_or_error.bg_image is None:
            contestant_model_or_error.bg_image = _get_random_bg_image(index)

        # Set buzz sound, if given
        contestant_model_or_error.buzz_sound = flask.request.form.get("buzz_sound")

        # Update or save contestant info
        if "default_avatar" not in flask.request.form and "avatar" in flask.request.files and flask.request.files["avatar"].filename:
            contestant_model_or_error.avatar = _save_contestant_avatar(flask.request.files["avatar"], user_id)

        model: Contestant = database.save_or_update(contestant_model_or_error, existing_model)

        if not user_already_joined:
            # If user isn't already in the game, add them
            game_contestant_model = GameContestant(
                game_id=game_data.id,
                contestant_id=model.id
            )
            database.add_contestant_to_game(game_contestant_model)

        response = flask.redirect(flask.url_for(".game_view", game_id=game_data.id, _external=True))

    # Save user ID to cookie
    cookie_id, data, max_age = _save_user_id_to_cookie(str(model.id))
    response.set_cookie(cookie_id, data, max_age=max_age)

    return response

@contestant_page.route("/<game_id>/game")
def game_view(game_id: str):
    user_id = _get_user_id_from_cookie(flask.request.cookies)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        game_data = database.get_game_from_id(game_id)
        if game_data is None:
            return render_locale_template("contestant/nogame.html", game_data.pack.language)

        # Validate that user_id is saved as a cookie
        if user_id is None:
            return flask.redirect(flask.url_for(".lobby", join_code=game_data.join_code, _external=True))

        # Find the game contestant matching the given user_id
        contestant_data = game_data.get_contestant(user_id)

        if contestant_data is None: # User haven't joined the game yet
            return flask.redirect(flask.url_for(".lobby", _external=True, join_code=game_data.join_code))

        # Get question data
        game_question = game_data.get_active_question()
        if game_question is not None:
            question = game_question.question.dump()
            question["daily_double"] = game_question.daily_double
        else:
            question = None

        round_name = game_data.pack.rounds[game_data.round - 1].name
        first_round = not game_data.get_active_question() and game_data.round == 1 and game_data.get_contestant_with_turn() is None

        game_json = game_data.dump(id="game_id")
        game_contestant_json = {}
        for game_contestant in game_data.game_contestants:
            if game_contestant.contestant_id == user_id:
                game_contestant_json = game_contestant.dump(id="user_id")

        total_questions = len(game_data.get_questions_for_round())

    return render_locale_template(
        "contestant/game.html",
        game_data.pack.language,
        ping=30,
        question=question,
        total_questions=total_questions,
        first_round=first_round,
        round_name=round_name,
        **game_json,
        **game_contestant_json,
    )

@contestant_page.route("/<join_code>")
def lobby(join_code: str):
    database: Database = flask.current_app.config["DATABASE"]

    with database:
        game_data = database.get_game_from_code(join_code)
        if game_data is None:
            return render_locale_template("contestant/nogame.html", game_data.pack.language)

        user_id = _get_user_id_from_cookie(flask.request.cookies)

        user_data = {}
        if user_id is not None:
            user_data = database.get_contestant_from_id(user_id).dump()

    if "avatar" not in user_data:
        user_data["avatar"] = get_avatar_path("questionmark.png")
        user_data["is_default_avatar"] = flask.url_for("static", filename="img/questionmark.png")

    error = flask.request.args.get("error")

    return render_locale_template(
        "contestant/lobby.html",
        game_data.pack.language,
        **user_data,
        join_code=join_code,
        has_password=game_data.password is not None,
        error=error,
    )
