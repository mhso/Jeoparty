import os
import shutil
import pytest

pytest.register_assert_rewrite("tests.browser_context")

from mhooge_flask.auth import get_hashed_password

from jeoparty.api.config import Config, get_question_pack_data_path, get_locale_data
from jeoparty.api.database import Database
from jeoparty.api.enums import Language
from jeoparty.api.orm.models import Contestant, QuestionPack, QuestionCategory, Question, QuestionRound, Theme
from tests.config import PRESENTER_USER_ID, PRESENTER_USERNAME, PRESENTER_PASSWORD

def _create_question_packs(database: Database):
    with database as session:
        # Create some themes
        theme_1 = Theme(
            id="5d374837-b817-4116-9644-c1046994ce37",
            name="Jul",
            language=Language.DANISH,
            created_by=PRESENTER_USER_ID,
        )

        theme_2 = Theme(
            id="87cfa214-1b9a-4edc-8ec8-fd66da1ae816",
            name="LAN",
            language=Language.DANISH,
            created_by=PRESENTER_USER_ID,
        )
        database.save_models(theme_1, theme_2)

        pack_model_1 = QuestionPack(
            name="Test Pack",
            created_by=PRESENTER_USER_ID,
        )
        pack_model_1 = database.create_question_pack(pack_model_1)
        os.mkdir(get_question_pack_data_path(pack_model_1.id))

        pack_model_1.rounds[1].round = 3
        extra_round = QuestionRound(
            pack_id=pack_model_1.id,
            name="Double Jeoparty!",
            round=2
        )
        database.save_models(extra_round, pack_model_1.rounds[1])
        session.refresh(pack_model_1)

        pack_model_2 = QuestionPack(
            name="Other Pack",
            public=True,
            include_finale=False,
            language=Language.DANISH,
            created_by=PRESENTER_USER_ID,
        )
        pack_model_2 = database.create_question_pack(pack_model_2)
        os.mkdir(get_question_pack_data_path(pack_model_2.id))

        shutil.copy(f"{Config.STATIC_FOLDER}/img/clock.png", f"{get_question_pack_data_path(pack_model_1.id)}/clock.png")
        shutil.copy(f"{Config.STATIC_FOLDER}/img/avatars/questionmark.png", f"{get_question_pack_data_path(pack_model_1.id)}/questionmark.png")

        category_model_1_1 = QuestionCategory(
            round_id=pack_model_1.rounds[0].id,
            name="Category Uno",
            order=0,
        )

        category_model_1_2 = QuestionCategory(
            round_id=pack_model_1.rounds[0].id,
            name="Category Dos",
            order=1,
        )

        category_model_2_1 = QuestionCategory(
            round_id=pack_model_1.rounds[1].id,
            name="Category Tres",
            order=0,
        )

        category_model_3_1 = QuestionCategory(
            round_id=pack_model_1.rounds[2].id,
            name="End of the Road",
            order=0,
        )

        database.save_models(category_model_1_1, category_model_1_2, category_model_2_1, category_model_3_1)

        question_model_1_1_1 = Question(
            category_id=category_model_1_1.id,
            question="What is the meaning of life, the universe, and everything?",
            answer="42",
            value=100,
            extra={"choices": ["42", "No idea", "Alcohol", "Eggs"], "explanation": "we all knew it"},
        )

        question_model_1_2_1 = Question(
            category_id=category_model_1_2.id,
            question="Where is Waldo?",
            answer="Where you least expect him",
            value=100,
            extra={"tips": ["Where is he not?"]}
        )

        question_model_1_2_2 = Question(
            category_id=category_model_1_2.id,
            question="What is time?",
            answer="An emergent property of entropy, maybe? Who knows, man",
            value=200,
            extra={"question_image": "clock.png", "height": "default"}
        )

        question_model_2_1_1 = Question(
            category_id=category_model_2_1.id,
            question="Dude, where is my car?",
            answer="Idk, haven't seen the movie",
            value=200,
        )

        question_model_2_1_2 = Question(
            category_id=category_model_2_1.id,
            question=(
                "Have you ever had a dream that where what he that where that "
                "uhm where uhm that he could do so much that you could do anything?"
            ),
            answer="I sure have, kid",
            value=400,
        )

        question_model_3_1_1 = Question(
            category_id=category_model_3_1.id,
            question="How many choices are in this question?",
            answer="4",
            value=300,
            extra={"question_image": "questionmark.png", "choices": ["1", "2", "3", "4"], "height": "small"}
        )

        database.save_models(
            question_model_1_1_1,
            question_model_1_2_1,
            question_model_1_2_2,
            question_model_2_1_1,
            question_model_2_1_2,
            question_model_3_1_1
        )

        return [pack_model_1.id, pack_model_2.id]

@pytest.fixture(scope="session")
def locales():
    # Load locale data
    return get_locale_data()

@pytest.fixture(scope="function")
def database():
    db_file = "test.db"
    db_file_path = f"{Config.RESOURCES_FOLDER}/{db_file}"
    if os.path.exists(db_file_path):
        os.remove(db_file_path)

    database = Database(db_file)

    with database:
        # Create presenter user
        hashed_pw = get_hashed_password(PRESENTER_PASSWORD, f"{Config.SRC_FOLDER}/app/static/secret.json")
        database.create_user(PRESENTER_USER_ID, PRESENTER_USERNAME, hashed_pw)

        # Create test contestant users
        colors = ["#ee1105", "#0564e8", "#35ae3b", "#9f1dd6", "#1565c6"]
        database.save_models(
            *[
                Contestant(id=f"contestant_id_{i}", name=f"Contestant {i}", color=color)
                for i, color in enumerate(colors)
            ]
        )

        pack_ids = _create_question_packs(database)

        yield database

    for pack_id in pack_ids:
        folder = get_question_pack_data_path(pack_id)
        shutil.rmtree(folder)

    database.engine.dispose()
    try:
       os.remove(db_file_path)
    except PermissionError:
        pass
