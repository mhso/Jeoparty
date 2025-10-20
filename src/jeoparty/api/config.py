import os
import re

def _get_project_folder():
    folder = os.getcwd()
    while not os.path.ismount(folder) and os.path.basename(folder) != "jeoparty":
        folder = os.path.dirname(folder)

    return os.path.abspath(folder)

class Config:
    ROUND_NAMES = [
        "Jeoparty!",
        "Double Jeoparty!",
        "Triple Jeoparty!",
    ]

    FINALE_NAME = "Final Jeoparty!"
    REGULAR_ROUNDS = 2

    PROJECT_FOLDER = _get_project_folder()
    SRC_FOLDER = f"{PROJECT_FOLDER}/src/jeoparty"

    STATIC_FOLDER = f"{SRC_FOLDER}/app/static"
    RESOURCES_FOLDER = f"{PROJECT_FOLDER}/resources/"

    DEFAULT_AVATAR = "questionmark.png"
    DEFAULT_CORRECT_IMAGE = "check.png"
    DEFAULT_WRONG_IMAGE = "check.png"

    ADMIN_ID = "71532753897030078646156925193385"

    VALID_NAME_CHARACTERS = re.compile(r"^[a-zA-Z0-9æøåÆØÅ_\-' ]*$")
    VALID_TITLE_CHARACTERS = re.compile(r"^[a-zA-Z0-9æøåÆØÅé_\/\-'!?\+\(\),\.:\& ]*$")

def get_question_pack_data_path(pack_id: str, full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/{pack_id}"

def get_avatar_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/avatars"

def get_buzz_sound_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/sounds"

def get_bg_image_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/backgrounds"

