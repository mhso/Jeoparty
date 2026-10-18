import os
import shutil
from subprocess import Popen
from time import sleep
import pytest
import requests
from sqlalchemy import text

pytest.register_assert_rewrite("tests.browser_context")

from mhooge_flask.auth import get_hashed_password
from mhooge_flask.database import Base

from jeoparty.api.config import Config, get_question_pack_data_path, get_locale_data
from jeoparty.api.database import Database
from jeoparty.api.enums import Environment, Language
from jeoparty.api.orm.models import Contestant, QuestionPack, QuestionCategory, Question, QuestionRound
from tests.config import PRESENTER_USER_ID, PRESENTER_USERNAME, PRESENTER_PASSWORD

def _create_question_packs(database: Database):
    with database as session:
        # Create some themes
        # theme_1 = Theme(
        #     id="5d374837-b817-4116-9644-c1046994ce37",
        #     name="Jul",
        #     language=Language.DANISH,
        #     created_by=PRESENTER_USER_ID,
        # )

        # theme_2 = Theme(
        #     id="87cfa214-1b9a-4edc-8ec8-fd66da1ae816",
        #     name="LAN",
        #     language=Language.DANISH,
        #     created_by=PRESENTER_USER_ID,
        # )
        # database.save_models(theme_1, theme_2)

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

@pytest.fixture(scope="session", autouse=True)
def create_dirs():
    if not os.path.exists(f"{Config.STATIC_FOLDER}/data/packs"):
        os.mkdir(f"{Config.STATIC_FOLDER}/data/packs")

@pytest.fixture(scope="session")
def locales():
    # Load locale data
    return get_locale_data()

@pytest.fixture(scope="session")
def config():
    return Config(Environment.TESTING)

@pytest.fixture(scope="function")
def database(config):
    database = Database(config)

    with database as session:
        # Drop and recreate tables
        Base.metadata.drop_all(database.engine)
        Base.metadata.create_all(database.engine)

        # Create presenter user
        hashed_pw = get_hashed_password(PRESENTER_PASSWORD, f"{config.STATIC_FOLDER}/secret.json")
        database.create_user(PRESENTER_USER_ID, PRESENTER_USERNAME, hashed_pw)

        session.execute(text(f"UPDATE themes SET created_by = '{PRESENTER_USER_ID}'"))
        session.execute(text(f"UPDATE question_packs SET created_by = '{PRESENTER_USER_ID}'"))
        session.commit()

        # Create test contestant users
        colors = ["#ee1105", "#0564e8", "#35ae3b", "#9f1dd6", "#1565c6"]
        database.save_models(
            *[
                Contestant(id=f"contestant_id_{i}", name=f"Contestant {i}", color=color)
                for i, color in enumerate(colors)
            ]
        )

        _create_question_packs(database)

        yield database

    database.engine.dispose()

def _wait_for_server():
    attempts = 20
    for _ in range(attempts):
        try:
            requests.get("http://localhost:5006/jeoparty/api/ping", timeout=1)
            return
        except requests.RequestException:
            sleep(0.5)

@pytest.fixture(scope="session", autouse=True)
def app():
    process = Popen(["uv", "run", "main.py", "-e" "testing"], cwd="src")
    _wait_for_server()

    yield

    process.terminate()
    process.wait()
