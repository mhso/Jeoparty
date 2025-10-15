import json

from jeoparty.api.database import Database
from jeoparty.api.orm.models import Game

database = Database()

with database:
    game_data = database.get_game_from_id("abf97d33-c55d-473e-aee8-724c0ceeb455")
    print(json.dumps(game_data.dump(included_relations=[Game.pack])))
