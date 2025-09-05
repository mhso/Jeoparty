from argparse import ArgumentParser
import os

from api.database import Database
from api.orm.models import QuestionPack, Game

parser = ArgumentParser()
parser.add_argument("jeopardy_iteration", type=int, choices=range(1, 6))
args = parser.parse_args()

os.remove("../resources/database.db")

database = Database()

pack_model = QuestionPack(
    name="LAN Jeopardy v1",
    created_by="user_123",
)

database.create_question_pack(pack_model)

game_model = Game(
    pack_id=pack_model.id,
    title="Jeoparty",
    max_contestants=4,
    created_by="user_123",
)

database.create_game(game_model)

print(pack_model.include_finale)

pack_model.include_finale = False

database.save_question_pack(pack_model)

print(game_model.pack.include_finale)
