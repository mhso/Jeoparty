from argparse import ArgumentParser
from datetime import datetime
import json

from api.database import Database
from api.enums import PowerUpType
from api.orm.models import *

version_choices = list(range(1, 6))

parser = ArgumentParser()
parser.add_argument("-i", "--iteration", type=int, choices=version_choices)
args = parser.parse_args()

extra_keys = [
    "image", "answer_image", "video", "height", "border", "explanation", "tips", "volume"
]
def get_question_extras(question: Dict[str, Any]):
    extra = {}
    for key in extra_keys:
        value = question.get(key)
        if key == "image":
            key = "question_image"

        if value is not None:
            extra[key] = value

    return extra or None

database = Database()
with database as session:
    versions = version_choices
    if args.iteration:
        versions = [args.iteration]

    for version in versions:
        questions_file = f"D:/mhooge/intfar/src/app/static/data/jeopardy_questions_{version}.json"

        user_id = "71532753897030078646156925193385"
        pack_dates = [
            (datetime(2023, 12, 8, 13, 0, 0), datetime(2023, 12, 29, 23, 0, 0)),
            (datetime(2024, 4, 15, 12, 0, 0), datetime(2024, 4, 26, 22, 0, 0)),
            (datetime(2025, 1, 25, 15, 0, 0), datetime(2025, 2, 8, 14, 0, 0)),
            (datetime(2025, 4, 18, 16, 0, 0), datetime(2025, 4, 26, 13, 0, 0)),
            (datetime(2025, 8, 9, 13, 0, 0), datetime(2025, 8, 23, 15, 0, 0)),
        ]
        rounds = [2, 2, 2, 1, 2]
        finale_categories = ["bois", "bois", "history", "history", "history"]

        with open(questions_file, "r", encoding="utf-8") as fp:
            questions_data = json.load(fp)

        created_date, changed_date = pack_dates[version - 1]

        pack_model = QuestionPack(
            name=f"LoL Jeopardy v{version}",
            created_by=user_id,
            created_at=created_date,
            changed_at=changed_date,
        )

        database.save_models(pack_model)

        round_models = [
            QuestionRound(
                pack_id=pack_model.id,
                name="Jeopardy!",
                round=1,
            ),
        ]
        if rounds[version - 1] == 2:
            round_models.append(
                QuestionRound(
                    pack_id=pack_model.id,
                    name="Double Jeopardy!",
                    round=2,
                )
            )

        round_models.append(
            QuestionRound(
                pack_id=pack_model.id,
                name="Final Jeopardy!",
                round=3,
            )
        )

        database.save_models(*round_models)

        finale_category = finale_categories[version - 1]

        category_models = []
        for category in questions_data:
            if category == finale_category:
                break

            category_data = questions_data[category]
            name = category_data["name"]
            order = category_data["order"]
            bg_image = category_data["background"]

            category_models.extend(
                [
                    QuestionCategory(
                        round_id=round_models[round_index].id,
                        name=name,
                        order=order,
                        bg_image=bg_image
                    )
                    for round_index in range(rounds[version - 1])
                ]
            )

        database.save_models(*category_models)

        question_models = []
        for index, category in enumerate(questions_data):
            if category == finale_category:
                break

            category_data = questions_data[category]
            buzz_time = category_data.get("buzz_time", 10)

            for tier_data in category_data["tiers"]:
                value = tier_data["value"]
                questions = tier_data["questions"]

                for round_index, question in enumerate(questions[:rounds[version - 1]]):
                    extra = get_question_extras(question)

                    category_id = category_models[index * rounds[version - 1] + round_index].id

                    question_model = Question(
                        category_id=category_id,
                        question=question["question"],
                        answer=question["answer"],
                        value=value,
                        buzz_time=buzz_time,
                        extra=extra,
                    )

                    question_models.append(question_model)

        database.save_models(*question_models)

        # Save finale data
        category_data = questions_data[finale_category]
        name = category_data["name"]
        order = category_data["order"]
        bg_image = category_data["background"]
        buzz_time = category_data.get("buzz_time", 10)

        finale_category = QuestionCategory(
            round_id=round_models[-1].id,
            name=name,
            order=order,
            bg_image=bg_image
        )

        database.save_models(finale_category)

        question = category_data["tiers"][-1]["questions"][0]
        extra = get_question_extras(question)
        finale_question = Question(
            category_id=finale_category.id,
            question=question["question"],
            answer=question["answer"],
            value=500,
            buzz_time=buzz_time,
            extra=extra,
        )

        database.save_models(finale_question)

        # Save power-ups
        power_ups = [
            PowerUp(
                pack_id=pack_model.id,
                type=power_type,
                icon=f"{power_type.value}_power.png",
                video=f"{power_type.value}_power_used.webm",
            )
            for power_type in PowerUpType
        ]

        database.save_models(*power_ups)
