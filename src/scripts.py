from argparse import ArgumentParser
import asyncio

from flask import json
import requests

from jeoparty.api.config import Config
from jeoparty.api.database import Database

class ScriptRunner:
    def fetch_resource(self):
        valid_image_filetypes = [
            "image/apng",
            "image/gif",
            "image/jpeg",
            "image/jpg",
            "image/pjpeg",
            "image/png",
            "image/webp",
        ]

        valid_video_filetypes = [
            "video/webm",
            "video/mp4",
        ]

        url = "https://imengine.public.mhm.infomaker.io/?uuid=422c3ae2-436b-531a-b1b1-07721245ec2f"

        # First try to do an 'options' request to just get content-type header
        response = requests.options(url)
        content_type = None

        all_valid_types = valid_image_filetypes + valid_video_filetypes

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type")

        if content_type is None or content_type not in all_valid_types:
            # If response is invalid, return error
            response = requests.get(url)
            if response.status_code != 200:
                print("It didn't work 2...", "Status:", response.status_code, response.text)
                return

            # If content-type was valid or 'options' request failed, get the full file
            content_type = response.headers.get("Content-Type")
            if content_type not in all_valid_types:
                print("It didn't work 3...", "Content-Type", content_type)
                return

            print("It worked!", content_type)

    def intfar_winner_call(self):
        player_data = [
            dict(
                game_id="id",
                name="Dave",
                color="#f30b0b",
                contestant_id="115142485579137029",
                score=800,
                buzzes=4,
                hits=2,
                misses=2,
            ),
            dict(
                game_id="id",
                name="Murt",
                color="#f30b0b",
                contestant_id="172757468814770176",
                score=500,
                buzzes=4,
                hits=3,
                misses=1,
            ),
            dict(
                game_id="id",
                contestant_id="331082926475182081",
                name="Muds",
                color="#f30b0b",
                score=-1200,
                buzzes=6,
                hits=1,
                misses=5,
            ),
            dict(
                game_id="id",
                name="Nø",
                color="#f30b0b",
                contestant_id="347489125877809155",
                score=-200,
                buzzes=1,
                hits=0,
                misses=1,
            )
        ]

        with open(f"{Config.STATIC_FOLDER}/secret.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)
            admin_id = data["intfar_disc_id"]
            token = data["intfar_user_id"]

        request_json = {"player_data": player_data, "disc_id": admin_id, "token": token}
        response = requests.post(f"http://localhost:5000/intfar/lan/jeopardy_winner", json=request_json)

        print(response.text, response.status_code)

    def delete_game(self, game_id: str):
        database = Database()
        database.delete_game(game_id)

if __name__ == "__main__":
    PARSER = ArgumentParser()

    TEST_RUNNER = ScriptRunner()
    FUNCS = [
        func
        for func in TEST_RUNNER.__dir__()
        if not func.startswith("_") and callable(getattr(TEST_RUNNER, func))
    ]

    PARSER.add_argument("func", choices=FUNCS)
    PARSER.add_argument("args", nargs="*")

    ARGS = PARSER.parse_args()

    func = getattr(TEST_RUNNER, ARGS.func)

    if asyncio.iscoroutinefunction(func):
        asyncio.run(func(*ARGS.args))
    else:
        func(*ARGS.args)
