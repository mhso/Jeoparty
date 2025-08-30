import flask
from mhooge_flask import routing, auth

login_page = flask.Blueprint("login", __name__)

@login_page.route("/", methods=["GET", "POST"])
def sign_in():
    if flask.request.method == "POST":
        # Login attempted.
        data = flask.request.form
        redirect_page = flask.request.args.pop("request_page")

        return auth.login(data, "user", "pass", redirect_page, "login.html", **flask.request.args)

    redirect_page = flask.request.args.pop("request_page")
    variables = {**flask.request.args}
    if redirect_page is None:
        redirect_page = "dashboard.home"

    # Display login form.
    redirect_url = flask.url_for(redirect_page, **variables, _external=True)
    return routing.make_template_context("login.html", status=200, redirect_url=redirect_url)
