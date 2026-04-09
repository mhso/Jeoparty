from argparse import ArgumentParser
import json
import socket
from os.path import basename
from glob import glob
from multiprocessing import Lock

import gevent

from mhooge_flask.logging import logger
from mhooge_flask import init
from mhooge_flask.init import Route, SocketIOServerWrapper
from mhooge_flask.restartable import restartable

from jeoparty.api.config import Config, Environment
from jeoparty.api.database import Database

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))

    ip = s.getsockname()[0]
    s.close()

    return ip

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

    if Config.ENV is Environment.DEVELOPMENT and not args.dev:
        host_url = get_local_ip()
        flask_url = "0.0.0.0"
    else:
        host_url = "localhost"
        flask_url = ""

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
        join_lock=Lock(),
        host_url=host_url,
    )
    logger.info("Starting Flask web app.")
    init.run_app(web_app, app_name, args.port, flask_url)

@restartable
def main():
    parser = ArgumentParser()
    parser.add_argument("-db", "--database", default="database.db")
    parser.add_argument("-d", "--dev", action="store_true")
    parser.add_argument("-p", "--port", type=int, default=5006)
    args = parser.parse_args()

    gevent.get_hub().NOT_ERROR += (KeyboardInterrupt,)
    run_app(args)

if __name__ == "__main__":
    main()
