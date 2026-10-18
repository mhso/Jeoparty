import flask
from mhooge_flask import auth
from mhooge_flask.routing import make_json_response

from jeoparty.api.config import Config
from jeoparty.api.enums import Environment

login_page = flask.Blueprint("login_api", __name__)

@login_page.route("/login", methods=["POST"])
def login():
    config: Config = flask.current_app.config["APP_CONFIG"]

    return auth.login_json(
        flask.request.form,
        "user",
        "pass",
        httponly=True,
        samesite="Lax",
        secure=config.env is Environment.PRODUCTION,
    )

@login_page.route("/signup", methods=["POST"])
def signup():
    config: Config = flask.current_app.config["APP_CONFIG"]

    return auth.signup_json(
        flask.request.form,
        "user",
        "pass",
        httponly=True,
        samesite="Lax",
        secure=config.env is Environment.PRODUCTION,
    )

@login_page.route("/logout", methods=["POST"])
def logout():
    user_details = auth.get_user_details()
    if user_details is None:
        return make_json_response("You are not logged in.", 200)

    flask.request.cookies.pop("jeoparty_token")

    return make_json_response("You have been successfully logged out.", 200)

@login_page.route("/me")
def me():
    user_details = auth.get_user_details()

    if user_details is None:
        return make_json_response("You are not authorized to access this content.", 401)

    user_id, user_name = user_details

    return make_json_response({"user_id": user_id, "user_name": user_name}, 200)
