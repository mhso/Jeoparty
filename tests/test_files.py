import os

from jinja2.environment import Environment
from jinja2.loaders import BaseLoader
from jinja2.exceptions import TemplateNotFound

from jeoparty.api.database import Database

class TemplateLoader(BaseLoader):
    def __init__(self):
        self.path = "src/jeoparty/app/templates"
        super().__init__()

    def get_source(self, environment, template):
        path = os.path.join(self.path, template)
        if not os.path.exists(path):
            raise TemplateNotFound(template)

        mtime = os.path.getmtime(path)
        with open(path) as f:
            source = f.read()

        return source, path, lambda: mtime == os.path.getmtime(path)

def url_for(endpoint, filename: str | None = None, _external: bool = True, **kwargs):
    final_endpoint = f"/{endpoint}"
    for v in kwargs.values():
        final_endpoint += f"/{v}"

    if filename is not None:
        final_endpoint += f"/{filename}"

    if _external:
        final_endpoint = f"127.0.0.1:5006/{final_endpoint}"

    return final_endpoint

def render_template(template_name, locale_data, **kwargs):
    page_key = template_name.split(".")[0]

    page_data = locale_data["pages"].get(page_key, {})
    page_data.update(locale_data["pages"].get("global", {}))
    kwargs["_locale"] = page_data

    jinja_env = Environment(loader=TemplateLoader())
    template = jinja_env.get_template(template_name)
    template.globals["url_for"] = url_for
    return template.render(**kwargs)

def find_files(html):
    pass

def _test_pages(locales):
    database = Database()

    global_vars = {
        "title": "Quiz Hour",
        "app_name": "Jeoparty"
    }

    # Sample data for contestants
    sample_contestants = [
        {
            "id": "contestant_1",
            "contestant_id": "user_1",
            "name": "Player One",
            "color": "#FF0000",
            "avatar": "img/avatars/default/avatar1.png",
            "score": 500,
            "buzzes": 3,
            "hits": 2,
            "misses": 1,
            "has_turn": True,
            "power_ups": [
                {"type": "hijack", "icon": "img/hijack_power.png", "used": False, "enabled": True},
                {"type": "freeze", "icon": "img/freeze_power.png", "used": False, "enabled": False},
                {"type": "rewind", "icon": "img/rewind_power.png", "used": True, "enabled": False}
            ]
        }
    ]
    
    pages = {
        "presenter/endscreen.html": {
            **global_vars,
            "game_id": "game123",
            "stage": "ended",
            "game_contestants": sample_contestants,
            "winners": [sample_contestants[0]],
            "winner_desc": "Player One wins the game!",
            "lan_mode": False,
            "theme": None,
            "created_by": "user123"
        },
        
        "presenter/finale.html": {
            **global_vars,
            "game_id": "game123",
            "stage": "finale_result",
            "game_contestants": sample_contestants,
            "category": {"name": "Final Category"},
            "question": "What is the answer?",
            "answer": "42",
            "theme": None,
            "created_by": "user123"
        },
        
        "presenter/lobby.html": {
            **global_vars,
            "game_id": "game123",
            "join_code": "quiz_hour",
            "join_url": "https://localhost/jeoparty/quiz_hour",
            "title": "Quiz Hour",
            "password": None,
            "game_contestants": [],
            "pack": {
                "lobby_music": None,
                "lobby_volume": None,
                "language": "english"
            },
            "lan_mode": False,
            "theme": None,
            "created_by": "user123",
            "stage": "lobby"
        },
        
        "presenter/question.html": {
            **global_vars,
            "game_id": "game123",
            "stage": "question",
            "round": 1,
            "total_rounds": 3,
            "round_name": "Round 1",
            "question_num": 1,
            "total_questions": 10,
            "game_contestants": sample_contestants,
            "category": {"name": "Test Category", "buzz_time": 10},
            "question": "What is 2+2?",
            "answer": "4",
            "value": 200,
            "extra": {"choices": ["3", "4", "5", "6"]},
            "daily_double": False,
            "question_ui_data": {
                "answer": "4",
                "value": 200,
                "answer_time": 6,
                "buzz_time": 10,
                "daily_double": False
            },
            "correct_image": "img/check.png",
            "wrong_image": "img/error.png",
            "correct_sound": "data/sounds/correct_answer.mp3",
            "wrong_sounds": ["data/sounds/wrong_answer.mp3"],
            "pack": {
                "power_ups": [
                    {"type": "hijack", "icon": "img/hijack_power.png", "video": "img/hijack_power_used_english.webm"},
                    {"type": "freeze", "icon": "img/freeze_power.png", "video": "img/freeze_power_used_english.webm"},
                    {"type": "rewind", "icon": "img/rewind_power.png", "video": "img/rewind_power_used_english.webm"}
                ]
            },
            "theme": None,
            "created_by": "user123"
        },
        
        "presenter/selection.html": {
            **global_vars,
            "game_id": "game123",
            "stage": "selection",
            "round": 1,
            "total_rounds": 3,
            "round_name": "Round 1",
            "first_round": False,
            "game_contestants": sample_contestants,
            "categories": [
                {
                    "name": "Category 1",
                    "questions": [
                        {"id": "q1", "value": 100, "used": False, "active": False, "daily_double": False},
                        {"id": "q2", "value": 200, "used": False, "active": False, "daily_double": False}
                    ]
                }
            ],
            "player_with_turn": sample_contestants[0],
            "lan_mode": False,
            "theme": None,
            "created_by": "user123",
            "name": "Final Jeoparty!"
        },
    }

    for lang in locales:
        for page in pages:
            html = render_template(page, locales[lang], **pages[page])
            files = find_files(html)
