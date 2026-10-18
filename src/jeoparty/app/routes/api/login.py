import flask
from mhooge_flask import auth

login_page = flask.Blueprint("login_api", __name__)

@login_page.route("/login", methods=["POST"])
def login():
    return auth.login_json(flask.request.form, "user", "pass")

@login_page.route("/signup", methods=["GET", "POST"])
def signup():
    return auth.signup_json(flask.request.form, "user", "pass")
