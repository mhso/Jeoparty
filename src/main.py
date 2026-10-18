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
    routes = []
    for prefix in ("", "api"):
        folder = f".{prefix}" if prefix else ""
        presenter = f"{prefix}/presenter" if prefix else "presenter"
        routes.extend(
            [
                Route("dashboard", "dashboard_page", prefix=prefix or "root", folder=f"routes{folder}"),
                Route("contestant", "contestant_page", prefix=prefix or "root", folder=f"routes{folder}"),
                Route("presenter", "presenter_page", presenter, folder=f"routes{folder}"),
                Route("login", "login_page", prefix=prefix or "root", folder=f"routes{folder}"),
            ]
        )

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
            server_cls=SocketIOServerWrapper,
            persistent_variables={"app_name": app_name.capitalize()},
            exit_code=0,
            app_config=config,
            locales=locale_data,
            join_lock=Lock(),
        )

        logger.info("Starting Flask web app.")
        init.run_app(web_app, app_name, args.port, config.flask_host_url)
    finally:
        if database and database.ssh_tunnel:
            database.ssh_tunnel.kill()
            database.ssh_tunnel.wait()

@restartable
def main():
    gevent.get_hub().NOT_ERROR += (KeyboardInterrupt,)

    parser = ArgumentParser()
    parser.add_argument("-e", "--env", type=str, choices=Environment)
    parser.add_argument("-p", "--port", type=int, default=5006)
    args = parser.parse_args()

    run_app(args)

if __name__ == "__main__":
    main()
