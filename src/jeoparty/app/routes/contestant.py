from glob import glob
import os
import random
from typing import Any, Dict, Tuple

import flask
from werkzeug.datastructures import FileStorage

from mhooge_flask.routing import make_template_context, make_json_response

from jeoparty.api.database import Database
from jeoparty.api.enums import StageType
from jeoparty.api.orm.models import Contestant, GameContestant
from jeoparty.app.routes.shared import create_and_validate_model, render_locale_template
from jeoparty.api.config import get_avatar_path, get_theme_path, get_bg_image_path, get_buzz_sound_path

contestant_page = flask.Blueprint("contestant", __name__, template_folder="templates")

_VALID_AVATAR_FILETYPES = set(["jpg", "jpeg", "png", "webp"])
COOKIE_ID = "jeoparty_contestant_id"

def _save_user_id_to_cookie(user_id: str):
    max_age = 60 * 60 * 24 * 365 # 1 year
    return COOKIE_ID, user_id, max_age

def _get_user_id_from_cookie(cookies) -> str:
    if (cid := cookies.get(COOKIE_ID)):
        return str(cid)

    return None

def _validate_join_params(params: Dict[str, Any]) -> Tuple[bool, Contestant | str]:
    if "join_code" not in params:
        return False, "Failed to join: Join code is missing"

    if "default_avatar" not in flask.request.form and "avatar" in flask.request.files and flask.request.files["avatar"].filename:
        file = flask.request.files["avatar"]
        file_split = file.filename.split(".")
        if len(file_split) != 2 or file_split[1] not in _VALID_AVATAR_FILETYPES:
            return False, "Invalid avatar file type, must be .jpg, .png, or .webp"

    return create_and_validate_model(Contestant, params, "joining lobby")

def _get_bg_image(index: int, image: str | None = None, theme_id: str | None = None):
    if image is not None:
        if theme_id:
            return f"{get_theme_path(theme_id, False)}/contestant_backgrounds/{image}"

        return f"{get_bg_image_path(False)}/{image}"

    files = []
    if theme_id:
        files = glob(f"{get_theme_path(theme_id)}/contestant_backgrounds/*")

    if files == []:
        files = glob(f"{get_bg_image_path()}/default/*")

    if files == []:
        return None

    files.sort()
    if index < len(files):
        file = files[index]
    else:
        file = files[random.randint(0, len(files) - 1)]

    return file.split("static/")[-1]

def _get_default_avatar(index: int, theme_id: str | None):
    files = []
    if theme_id:
        files = glob(f"{get_theme_path(theme_id)}/avatars/*")

    if files == []:
        files = glob(f"{get_avatar_path()}/default/*")

    if index < len(files):
        files.sort()
        return files[index].split("static/")[-1]

    return None

def _save_contestant_avatar(file: FileStorage, user_id: str):
    file_split = file.filename.split(".")
    filename = f"{user_id}.{file_split[1]}"
    path = os.path.join(get_avatar_path(), filename)

    file.save(path)

    return f"{get_avatar_path(False)}/{filename}"

@contestant_page.route("/join", methods=["POST"])
def join_lobby():
    database: Database = flask.current_app.config["DATABASE"]

    user_id = flask.request.form.get("user_id")
    params = dict(flask.request.form)

    if user_id is not None:
        params["id"] = user_id

    success, contestant_model_or_error = _validate_join_params(params)
    join_code = flask.request.form.get("join_code")

    if not success:
        if join_code is None:
            return make_json_response({"error": "Failed to join: Missing join code"}, 400)

        return make_json_response({"error": contestant_model_or_error}, 400)

    contestant_model: Contestant = contestant_model_or_error

    with database as session:
        game_data = database.get_game_from_code(join_code)
        if game_data is None:
            return make_json_response({"error": "Failed to join: Game does not exist"}, 404)

        if game_data.password is not None and flask.request.form.get("password") != game_data.password:
            return make_json_response({"error": "Failed to join: Wrong password"}, 401)

        if game_data.stage == StageType.ENDED:
            return make_json_response({"error": "Failed to join: Game is over"}, 400)

        # Ensure no race conditions can occur when contestants join
        with flask.current_app.config["JOIN_LOCK"]:
            session.refresh(game_data)

            index = len(game_data.game_contestants)
            if index == game_data.max_contestants:
                return make_json_response({"error": "Failed to join: Lobby is full"}, 400)

            # Try to get existitng user
            existing_model = None if user_id is None else database.get_contestant_from_id(user_id)

            user_already_joined = False
            if existing_model is not None:
                contestant_model.id = existing_model.id
                contestant_model.avatar = existing_model.avatar
                contestant_model.bg_image = existing_model.bg_image
                contestant_model.buzz_sound = existing_model.buzz_sound

                for contestant in game_data.game_contestants:
                    if contestant.contestant_id == user_id:
                        user_already_joined = True
                        break

            # Get or set background image
            bg_image = flask.request.form.get("bg_image")
            bg_image = _get_bg_image(index, bg_image, game_data.pack.theme_id)

            contestant_model.bg_image = bg_image

            # Set buzz sound, if given
            buzz_sound = flask.request.form.get("buzz_sound")
            if buzz_sound is not None:
                contestant_model.buzz_sound = f"{get_buzz_sound_path(game_data.pack.theme_id, False)}/{buzz_sound}"

            # We need the ID of the user to use in the filename of their avatar,
            # so we have to save the contestant twice
            contestant_model = database.save_or_update(contestant_model, existing_model)

            # Update or save contestant avatar
            new_avatar = None
            if "default_avatar" not in flask.request.form and "avatar" in flask.request.files and flask.request.files["avatar"].filename:
                new_avatar = _save_contestant_avatar(flask.request.files["avatar"], contestant_model.id)
            elif existing_model is None or existing_model.avatar is None:
                new_avatar = _get_default_avatar(index, game_data.pack.theme_id)

            if new_avatar is not None:
                contestant_model.avatar = new_avatar
                database.save_models(contestant_model)

            if not user_already_joined:
                # If user isn't already in the game, add them
                game_contestant_model = GameContestant(
                    game_id=game_data.id,
                    contestant_id=contestant_model.id
                )
                database.add_contestant_to_game(game_contestant_model, game_data.use_powerups)

        response = make_json_response({"redirect": flask.url_for(".game_view", game_id=game_data.id, _external=True)}, 200)

        # Save user ID to cookie
        cookie_id, data, max_age = _save_user_id_to_cookie(str(contestant_model.id))
        response.set_cookie(cookie_id, data, max_age=max_age, samesite="Lax")
        response.headers.add_header("Access-Control-Allow-Credentials", "true")

    return response

@contestant_page.route("/<game_id>/game")
def game_view(game_id: str):
    user_id = _get_user_id_from_cookie(flask.request.cookies)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        game_data = database.get_game_from_id(game_id)
        if game_data is None:
            return make_template_context("contestant/nogame.html", status=404)

        # Validate that user_id is saved as a cookie
        if user_id is None:
            return flask.redirect(flask.url_for(".lobby", join_code=game_data.join_code, _external=True))

        # Find the game contestant matching the given user_id
        contestant_data = game_data.get_contestant(contestant_id=user_id)

        if contestant_data is None: # User haven't joined the game yet
            return flask.redirect(flask.url_for(".lobby", join_code=game_data.join_code, _external=True))

        # Get question data
        game_question = game_data.get_active_question()
        if game_question is not None:
            question = game_question.question.dump() 
            question["category"] = game_question.question.category.dump(included_relations=[])
            question["daily_double"] = game_question.daily_double
        else:
            question = None

        round_name = game_data.pack.rounds[game_data.round - 1].name
        first_round = not game_data.get_active_question() and game_data.round == 1 and game_data.get_contestant_with_turn() is None

        game_json = game_data.dump(included_relations=[], id="game_id")

        game_contestant_json = contestant_data.dump(id="user_id")

        # If game is ended, save whether this contestant won
        if game_data.stage == StageType.ENDED:
            winners = game_data.get_game_winners()
            contestant_won = False
            for winner_data in winners:
                if winner_data.id == contestant_data.id:
                    contestant_won = True

            game_contestant_json["winner"] = contestant_won

        num_questions_in_round = len(game_data.get_questions_for_round())

        return render_locale_template(
            "contestant/game.html",
            game_data.pack.language,
            ping=30,
            question=question,
            num_questions_in_round=num_questions_in_round,
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
            return make_template_context("contestant/nogame.html", status=404)

        user_id = _get_user_id_from_cookie(flask.request.cookies)

        user_data = {}
        if user_id is not None:
            user_data = database.get_contestant_from_id(user_id).dump()

    if "avatar" not in user_data:
        user_data["avatar"] = f"{get_avatar_path(False)}/questionmark.png"
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
