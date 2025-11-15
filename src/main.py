from argparse import ArgumentParser
import json
from os.path import basename
from glob import glob
import gevent

from mhooge_flask.logging import logger
from mhooge_flask import init
from mhooge_flask.init import Route, SocketIOServerWrapper
from mhooge_flask.restartable import restartable

from jeoparty.api.config import Config
from jeoparty.api.database import Database

def run_app(args):
    routes = [
        Route("dashboard", "dashboard_page"),
        Route("contestant", "contestant_page"),
        Route("presenter", "presenter_page", "presenter"),
        Route("login", "login_page")
    ]

    database = Database(args.database)
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
        locales=locale_data,
    )

    ports_file = f"{Config.PROJECT_FOLDER}/../flask_ports.json"

    logger.info("Starting Flask web app.")

    init.run_app(web_app, app_name, ports_file)

@restartable
def main():
    parser = ArgumentParser()
    parser.add_argument("-db", "--database", default="database.db")
    args = parser.parse_args()

    gevent.get_hub().NOT_ERROR += (KeyboardInterrupt,)
    run_app(args)

if __name__ == "__main__":
    main()
