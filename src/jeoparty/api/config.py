from glob import glob
import json
import os
import re
import socket

from jeoparty.api.enums import Environment

def _get_project_folder():
    folder = os.getcwd()
    while not os.path.ismount(folder) and os.path.basename(folder) != "jeoparty":
        folder = os.path.dirname(folder)

    return os.path.abspath(folder)

def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))

    ip = s.getsockname()[0]
    s.close()

    return ip

class Config:
    # Static Paths
    PROJECT_FOLDER = _get_project_folder()
    SRC_FOLDER = f"{PROJECT_FOLDER}/src"
    STATIC_FOLDER = f"{SRC_FOLDER}/jeoparty/app/static"
    RESOURCES_FOLDER = f"{PROJECT_FOLDER}/resources"
    # Output of `npm run build` in the jeoparty_web repo, served by routes/spa.py
    FRONTEND_DIST_FOLDER = os.environ.get(
        "JEOPARTY_FRONTEND_DIST", os.path.abspath(f"{PROJECT_FOLDER}/../jeoparty_web/dist")
    )

    # Static regexes for valid titles and names
    VALID_NAME_CHARACTERS = re.compile(r"^[a-zA-Z0-9æøåÆØÅ_\-' ]*$")
    VALID_TITLE_CHARACTERS = re.compile(r"^[a-zA-Z0-9æøåÆØÅé_\/\-'!?\+\(\),\.:\&\% ]*$")

    # Static default question values
    DEFAULT_ROUND_NAMES = [
        "Jeoparty!",
        "Double Jeoparty!",
        "Triple Jeoparty!",
    ]
    DEFAULT_FINALE_NAME = "Final Jeoparty!"
    DEFAULT_REGULAR_ROUNDS = 2
    DEFAULT_ANSWER_TIME = 6
    MAX_ANSWER_CHOICES = 8

    # Default filenames
    DEFAULT_AVATAR = "questionmark.png"
    DEFAULT_CORRECT_IMAGE = "check.png"
    DEFAULT_WRONG_IMAGE = "check.png"

    # Predefined sizes of question images/videos,
    # relative to the viewheight of the screen
    QUESTION_MEDIA_SIZES = {
        "small": 26,
        "default": 42,
        "maximized": 70,
    }

    ADMIN_ID = "71532753897030078646156925193385"

    def __init__(self, env: Environment | None = None) -> None:
        with open(f"{Config.STATIC_FOLDER}/secret.json", "r", encoding="utf-8") as fp:
            secrets = json.load(fp)

        self.env = Environment(secrets["env"]) if env is None else env
        self.db_password = secrets["database_password"]

    @property
    def internal_host_url(self):
        return "http://localhost" if self.env is Environment.DEVELOPMENT else "https://mhooge.com"

    @property
    def external_host_url(self):
        return f"http://{_get_local_ip()}:5006" if self.env is Environment.DEVELOPMENT else "https://mhooge.com"

    @property
    def flask_host_url(self):
        return "0.0.0.0" if self.env is Environment.DEVELOPMENT else ""

    @property
    def db_conn_str(self):
        db_name = f"jeoparty_{self.env.value}"
        db_password = "password" if self.env is Environment.TESTING else self.db_password

        return f"postgresql+psycopg://mikkel:{db_password}@localhost:5432/{db_name}?connect_timeout=5&"

def get_question_pack_data_path(pack_id: str, full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/packs/{pack_id}"

def get_avatar_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/avatars"

def get_buzz_sound_path(theme_id: str | None, full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    if theme_id:
        return f"{prefix}data/themes/{theme_id}/sounds"
    return f"{prefix}data/sounds"

def get_bg_image_path(full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}img/backgrounds"

def get_theme_path(theme: str, full: bool = True):
    prefix = f"{Config.STATIC_FOLDER}/" if full else ""
    return f"{prefix}data/themes/{theme}"

def get_locale_data():
    locale_data = {}
    for filename in glob(f"{Config.RESOURCES_FOLDER}/locales/*.json"):
        lang = os.path.basename(filename).split(".")[0]
        with open(filename, "r", encoding="utf-8") as fp:
           locale_data[lang] = json.load(fp)

    return locale_data

def file_or_fallback(file: str, fallback: str, condition: bool):
    if condition and os.path.exists(f"{Config.STATIC_FOLDER}/{file}"):
        return file

    return fallback
