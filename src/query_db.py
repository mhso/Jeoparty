from argparse import ArgumentParser
import json

from jeoparty.api.config import Config
from jeoparty.api.enums import Environment
from jeoparty.api.database import Database

from mhooge_flask.query_db import query_or_repl

with open(f"{Config.STATIC_FOLDER}/secret.json", "r", encoding="utf-8") as fp:
    secrets = json.load(fp)

parser = ArgumentParser()

parser.add_argument("-e", "--env", default=secrets["env"])
parser.add_argument("--query", default=None, type=str, nargs="+")
parser.add_argument("--raw", action="store_true")
parser.add_argument("--print", action="store_true")

args = parser.parse_args()

env = Environment(args.env)

database = Database(Config(env))

query_or_repl(database, args.query, args.raw, args.print)
