from argparse import ArgumentParser
import json
from os.path import basename
from glob import glob
from multiprocessing import Lock

import gevent

from mhooge_flask.logging import logger
from mhooge_flask import init
from mhooge_flask.init import Route, SocketIOServerWrapper
from mhooge_flask.restartable import restartable

from jeoparty.api.config import Config
from jeoparty.api.enums import Environment
from jeoparty.api.database import Database

def run_app(args):
    if args.spa:
        # Built Vue frontend instead of the Jinja pages (see routes/spa.py)
        page_routes = [Route("spa", "spa_page")]
    else:
        page_routes = [
            Route("dashboard", "dashboard_page"),
            Route("contestant", "contestant_page"),
            Route("presenter", "presenter_page", prefix="presenter"),
            Route("login", "login_page"),
        ]

    routes = page_routes + [
        Route("dashboard", "dashboard_page", prefix="api", folder="routes.api"),
        Route("contestant", "contestant_page", prefix="api", folder="routes.api"),
        Route("game", "game_page", prefix="api", folder="routes.api"),
        Route("auth", "auth_page", prefix="api", folder="routes.api"),
    ]

    override_env = None
    if args.env:
        override_env = Environment(args.env)

    config = Config(override_env)

    logger.info(f"Running in **{config.env.value}** mode")

    database = None
    try:
        database = Database(config)
        app_name = "jeoparty"

        locale_data = {}
        for filename in glob(f"{Config.RESOURCES_FOLDER}/locales/*.json"):
            lang = basename(filename).split(".")[0]
            with open(filename, "r", encoding="utf-8") as fp:
                locale_data[lang] = json.load(fp)

        # Create Flask app.
        web_app = init.create_app(
            app_name,
            f"/{app_name}/",
            routes,
            database,
            root_folder="jeoparty/app",
            static_path="/jeoparty/static",
            static_folder="static",
            server_cls=SocketIOServerWrapper,
            persistent_variables={"app_name": app_name.capitalize()},
            exit_code=0,
            app_config=config,
            locales=locale_data,
            join_lock=Lock(),
        )

        logger.info("Starting Flask web app.")
        init.run_app(web_app, app_name, args.port, config.flask_host_url)
    except KeyboardInterrupt:
        pass
    finally:
        if database and database.ssh_tunnel:
            database.ssh_tunnel.terminate()
            database.ssh_tunnel.kill()
            database.ssh_tunnel.wait()

@restartable
def main():
    gevent.get_hub().NOT_ERROR += (KeyboardInterrupt,)

    parser = ArgumentParser()
    parser.add_argument("-e", "--env", type=str, choices=Environment)
    parser.add_argument("-p", "--port", type=int, default=5006)
    parser.add_argument("--spa", action="store_true", help="Serve the built Vue frontend instead of the Jinja templates")
    args = parser.parse_args()

    run_app(args)

if __name__ == "__main__":
    main()
