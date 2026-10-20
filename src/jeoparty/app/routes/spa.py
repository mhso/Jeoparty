"""
Serves the built Vue frontend (jeoparty_web/dist) in place of the Jinja routes.
Each URL gets one of the three entry HTML files and that entry's client-side
router takes it from there. See the routing table in API_BLUEPRINT.md §8; the
dev-server equivalent is `entryFor` in jeoparty_web/vite.config.ts.

The contestant catch-all relies on Werkzeug ranking `<path:...>` below every
other rule, so the API blueprints and /static always win.
"""
import flask

from jeoparty.api.config import Config

spa_page = flask.Blueprint("spa", __name__)

# Must match `DASHBOARD_PATH` in vite.config.ts.
_DASHBOARD_PATHS = [
    "/",
    "/login",
    "/create_game",
    "/create_pack",
    "/pack/<pack_id>",
    "/pack/<pack_id>/cheatsheet",
]

def _serve_entry(entry: str):
    response = flask.send_from_directory(Config.FRONTEND_DIST_FOLDER, entry)
    # The HTML references content-hashed assets, so it must never be cached itself.
    response.headers["Cache-Control"] = "no-cache"
    return response

@spa_page.route("/presenter/<path:path>")
def presenter(path: str):
    return _serve_entry("presenter.html")

def dashboard(**_):
    return _serve_entry("dashboard.html")

for _path in _DASHBOARD_PATHS:
    spa_page.add_url_rule(_path, "dashboard", dashboard)

@spa_page.route("/<path:path>")
def contestant(path: str):
    # A typo'd API call should fail loudly, not get a 200 with contestant.html.
    if path.startswith("api/"):
        flask.abort(404)

    # Built files (dist/assets/...) live under the same prefix as the pages.
    # Anything that looks like a file but doesn't exist is a 404, not a join code.
    if "." in path.rsplit("/", 1)[-1]:
        return flask.send_from_directory(Config.FRONTEND_DIST_FOLDER, path)

    return _serve_entry("contestant.html")
