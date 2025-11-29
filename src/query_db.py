from argparse import ArgumentParser
import os

from jeoparty.api.config import Config
from jeoparty.api.database import Database

from mhooge_flask.query_db import query_or_repl

parser = ArgumentParser()

parser.add_argument("-db", "--database", default="database.db")
parser.add_argument("--query", default=None, type=str, nargs="+")
parser.add_argument("--raw", action="store_true")
parser.add_argument("--print", action="store_true")

args = parser.parse_args()

if not os.path.exists(f"{Config.RESOURCES_FOLDER}/{args.database}"):
    print("Database does not seem to exist. Exiting...")
    exit(0)

database = Database(args.database)

query_or_repl(database, args.query, args.raw, args.print)
