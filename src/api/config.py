import os

def _get_project_folder():
    folder = os.getcwd()
    while os.path.basename(folder) != "jeoparty":
        folder = os.path.join(os.path.pardir, folder)

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

    STATIC_FOLDER = f"{PROJECT_FOLDER}/app/static"
    RESOURCES_FOLDER = f"{PROJECT_FOLDER}/resources/"

    DEFAULT_AVATAR = "questionmark.png"
    DEFAULT_CORRECT_IMAGE = "check.png"
    DEFAULT_WRONG_IMAGE = "check.png"

    ADMIN_ID = "71532753897030078646156925193385"

def get_data_path_for_question_pack(pack_id: str, full: bool = True):
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

