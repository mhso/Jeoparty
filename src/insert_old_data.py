from argparse import ArgumentParser
import os

from api.database import Database
from api.orm.models import QuestionPack, Game

parser = ArgumentParser()
parser.add_argument("jeopardy_iteration", type=int, choices=range(1, 6))
args = parser.parse_args()

#os.remove("../resources/database.db")

database = Database()

# model = QuestionPack(
#     name="LAN Jeopardy v1",
#     created_by="user_123",
# )

# database.create_question_pack(model)

game_model = Game(
    pack_id="68292b53-6c2b-48f5-b10a-b2c2629f5df1",
    title="Jeoparty",
    max_contestants=4,
    created_by="user_123",
)

database.create_game(game_model)