from argparse import ArgumentParser
from datetime import datetime
import os

from api.database import Database
from api.orm.models import *

parser = ArgumentParser()
parser.add_argument("jeopardy_iteration", type=int, choices=range(1, 6))
args = parser.parse_args()

os.remove("../resources/database.db")

database = Database()

user_id = "73684529367910817247612734198186"

with database as session:
    pack_model = QuestionPack(
        name="LAN Jeopardy v1",
        created_by=user_id,
        created_at=datetime(2023, 12, 8, 13, 0, 0),
        changed_at=datetime(2023, 12, 29, 23, 0, 0),
    )

    database.create_question_pack(pack_model)

    round_models = [
        QuestionRound(
            pack_id=pack_model.id,
            name="Jeopardy!",
            round=1,
        ),
        QuestionRound(
            pack_id=pack_model.id,
            name="Double Jeopardy!",
            round=2,
        ),
        QuestionRound(
            pack_id=pack_model.id,
            name="Final Jeopardy!",
            round=3,
        ),
    ]

    for round_model in round_models:
        database.save_model(round_models)


