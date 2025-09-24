import os
import pytest

from src.api.config import Config
from src.api.database import Database
from src.api.orm.models import Contestant

@pytest.fixture(scope="function")
def database():
    db_file = "test.db"
    database = Database(db_file)

    # Create presenter user
    database.create_user("User 123", "Presenter", "hashed_pw_123")

    # Create test contestant users
    database.save_contenstant(
        Contestant(
            id="contestant_id_1",
            name="Contestant 1",
            color="#ee1105",
        )
    )

    yield database

    os.remove(f"{Config.RESOURCES_FOLDER}/{db_file}")
