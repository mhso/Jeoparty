import flask
from mhooge_flask import routing, auth

login_page = flask.Blueprint("login", __name__)

@login_page.route("/login", methods=["GET", "POST"])
def login():
    redirect_page = flask.request.args.get("redirect_url", "dashboard.home")
    if redirect_page == "":
        redirect_page = "dashboard.home"

    redirect_args = {arg: flask.request.args[arg] for arg in flask.request.args if arg != "redirect_page"}

    if flask.request.method == "POST":
        # Login attempted.
        data = flask.request.form

        return auth.login(data, "user", "pass", redirect_page, "login.html", **redirect_args)

    # Display login form.
    redirect_url = flask.url_for(redirect_page, **redirect_args, _external=True)
    return routing.make_template_context("login.html", status=200, redirect_url=redirect_url)

@login_page.route("/signup", methods=["GET", "POST"])
def signup():
    if flask.request.method == "POST":
        # Sign up attempted.
        data = flask.request.form

        return auth.signup(data, "user", "pass", "dashboard.home", "login.html")

    # Display login form.
    error = flask.request.args.get("error")
    return routing.make_template_context("login.html", status=200, error=error)
