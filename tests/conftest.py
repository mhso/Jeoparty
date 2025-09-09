import os
import shutil
import pytest

from src.api.database import Database
from src.api.config import Config
from src.api.orm.models import Contestant

@pytest.fixture()
def database():
    db_file = "test.db"
    test_db_path = f"{Config.RESOURCES_FOLDER}/{db_file}"
    real_db_path = f"{Config.RESOURCES_FOLDER}/database.db"

    shutil.copy(real_db_path, test_db_path)

    database = Database(db_file)

    # Create presenter user
    database.create_user("user_123", "Presenter", "hashed_pw_123")
    
    # Create contestant  users
    database.save_contenstant(Contestant())

    yield database

    os.remove(f"{Config.RESOURCES_FOLDER}/{db_file}")
