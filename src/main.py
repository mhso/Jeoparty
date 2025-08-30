import json
from mhooge_flask.logging import logger
from mhooge_flask import init
from mhooge_flask.init import Route
from mhooge_flask.restartable import restartable

from api.database import Database

@restartable
def main():
    routes = [
        Route("dashboard", "dashboard_page"),
        Route("contestant", "contestant_page"),
        Route("presenter", "presenter_page", "presenter"),
        Route("login", "login_page", "login")
    ]

    database = Database()
    app_name = "jeopardy"

    # Create Flask app.
    web_app = init.create_app(
        app_name,
        f"/{app_name}/",
        routes,
        database,
        join_locks={},
        buzz_locks={},
        exit_code=0
    )

    ports_file = "../../flask_ports.json"

    logger.info("Starting Flask web app.")

    init.run_app(web_app, app_name, ports_file)

if __name__ == "__main__":
    main()
