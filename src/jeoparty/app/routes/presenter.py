import random

import flask
from flask import json
from mhooge_flask.auth import get_user_details
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io
import requests

from jeoparty.api.database import Database
from jeoparty.api.config import Config
from jeoparty.api.enums import StageType
from jeoparty.api.orm.models import Game, GameQuestion
from jeoparty.app.routes.socket import GameSocketHandler, get_namespace_handler
from jeoparty.app.routes.shared import (
    redirect_to_login,
    render_locale_template,
    get_question_answer_sounds,
    get_question_answer_images,
)

presenter_page = flask.Blueprint("presenter", __name__, template_folder="templates")

def _is_lan_active(game_data: Game):
    return (
        game_data.pack.theme is not None
        and game_data.pack.theme.name == "LAN"
        and game_data.created_by == Config.ADMIN_ID
    )

def _request_decorator(func):
    """
    Decorator for ensuring the following before a request:
    - The user is logged in and authorized
    - Game data exists and is cached
    - SocketIO namespace is set up for the given game
    """
    def wrapper(*args, **kwargs):
        game_id = kwargs.pop("game_id")

        # Setup socket namespace for the given game
        namespace_handler = get_namespace_handler(game_id)

        database: Database = flask.current_app.config["DATABASE"]
        with database:
            # Ensure user is logged in or redirect to login
            if (user_details := get_user_details()) is None:
                return redirect_to_login(f"presenter.{func.__name__}", game_id=game_id)

            # Retrieve the game data for the given game ID or abort if it is missing
            game_data = database.get_game_from_id(game_id)
            if game_data is None:
                return flask.abort(404)

            # Verify the user actually created the game
            if user_details[0] != game_data.created_by:
                return flask.abort(401)

            if namespace_handler is None:
                namespace_handler = GameSocketHandler(game_data.id, database)
                socket_io.on_namespace(namespace_handler)

            namespace_handler.game_metadata.presenter_joined = False

            # Inject game data to the route handler
            return func(game_data=game_data, *args, **kwargs)

    wrapper.__setattr__("__name__", func.__name__)

    return wrapper

@presenter_page.route("/<game_id>")
@_request_decorator
def lobby(game_data: Game):
    join_url = f"mhooge.com/jeoparty/{game_data.join_code}"

    game_json = game_data.dump(included_relations=[Game.pack, Game.game_contestants], id="game_id")

    return render_locale_template(
        "presenter/lobby.html",
        game_data.pack.language,
        join_url=join_url,
        lan_mode=_is_lan_active(game_data),
        **game_json,
    )

@presenter_page.route("/<game_id>/question")
@_request_decorator
def question(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    game_question: GameQuestion | None = game_data.get_active_question()
    if game_question is None or game_question.used:
        # If question does not exist or has already been answered, redirect back to selection
        return flask.redirect(flask.url_for(".selection", game_id=game_data.id))

    question_json = game_question.question.dump(id="question_id")
    question_json["category"] = game_question.question.category.dump(included_relations=[])
    question_json["daily_double"] = game_question.daily_double

    # Data used as variables in JS for controlling presenter UI flow
    question_ui_data = {
        "answer": question_json["answer"],
        "value": question_json["value"],
        "answer_time": game_data.answer_time,
        "buzz_time": question_json["category"]["buzz_time"],
        "daily_double": question_json["daily_double"],
    }

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_json["extra"]:
        random.shuffle(question_json["extra"]["choices"])

    # Set stage to 'question' or 'finale_question'
    game_data.stage = StageType.FINALE_QUESTION if game_data.stage == StageType.FINALE_WAGER else StageType.QUESTION

    # Disable all power-ups except hijack unless question is daily double or we are at the finale
    for contestant in game_data.game_contestants:
        for power_up in contestant.power_ups:
            power_up.enabled = False

        database.save_models(*contestant.power_ups)

    database.save_game(game_data)

    # Get images and sounds for when questions are answered correctly/wrong
    correct_image, wrong_image = get_question_answer_images(game_data.pack.theme)
    correct_sound, wrong_sounds = get_question_answer_sounds(game_data.pack.theme, game_data.max_contestants)

    round_name = game_data.pack.rounds[game_data.round - 1].name
    game_json = game_data.dump(included_relations=[Game.pack, Game.game_contestants], id="game_id")

    return render_locale_template(
        "presenter/question.html",
        game_data.pack.language,
        correct_image=correct_image,
        wrong_image=wrong_image,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        round_name=round_name,
        media_sizes=Config.QUESTION_MEDIA_SIZES,
        question_ui_data=question_ui_data,
        **game_json,
        **question_json,
    )

@presenter_page.route("/<game_id>/selection")
@_request_decorator
def selection(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    # Get currently active question (if any) and mark it as inactive and used
    previous_question = game_data.get_active_question()
    if previous_question:
        previous_question.used = True
        previous_question.active = False
        database.save_models(previous_question)

    # Set game stage to 'selection'
    game_data.stage = StageType.SELECTION

    # Check if we are done with all questions in the current round
    questions = game_data.get_questions_for_round()
    end_of_round = questions != [] and all(question.used for question in questions)

    is_finale = False
    if end_of_round:
        # Round done, onwards to the next one!
        game_data.round += 1

        if game_data.round > game_data.regular_rounds:
            if not game_data.pack.include_finale:
                # No finale, so game is over. Redirect directly to endscreen
                return flask.redirect(flask.url_for(".endscreen", game_id=game_data.id))

            is_finale = True

        else:
            # The player with the lowest score at the start of a new regular round gets the turn
            lowest_score = 0
            lowest_score_id = game_data.game_contestants[0].contestant_id
            for contestant in game_data.game_contestants:
                if contestant.score < lowest_score:
                    lowest_score_id = contestant.contestant_id
                    lowest_score = contestant.score

            game_data.set_contestant_turn(lowest_score_id)

        if is_finale:
            game_data.stage = StageType.FINALE_WAGER
            if game_data.round < len(game_data.pack.rounds):
                # If the game has less rounds than the question pack
                # and this round is the finale, set the round to equal
                # the last round of the pack
                game_data.round = len(game_data.pack.rounds)

        questions = game_data.get_questions_for_round()

    if is_finale:
        # Set the single finale question as the active question
        questions[0].active = True

    first_round = not previous_question and game_data.round == 1 and game_data.get_contestant_with_turn() is None
    if (not previous_question or end_of_round) and not is_finale:
        # If it's the first question of a new round, select random questions to be daily doubles
        if game_data.use_daily_doubles:
            questions_copy = list(questions)
            random.shuffle(questions_copy)

            round_zero = game_data.round - 1
            dailies_in_round = (game_data.regular_rounds + 1) - (game_data.regular_rounds - round_zero)

            for index, game_question in enumerate(questions_copy):
                game_question.daily_double = index < dailies_in_round

            database.save_models(*questions_copy)

        # Reset used power-ups
        for contestant in game_data.game_contestants:
            if contestant.power_ups:
                for power_up in contestant.power_ups:
                    power_up.used = False

                database.save_models(*contestant.power_ups)

    round_data = game_data.pack.rounds[game_data.round - 1]
    round_json = round_data.dump(id="round_id")
    del round_json["round"]

    # Merge data about game questions and actual questions
    for category_json in round_json["categories"]:
        for question_json in category_json["questions"]:
            for game_question in questions:
                if game_question.question_id == question_json["id"]:
                    question_json["active"] = game_question.active
                    question_json["used"] = game_question.used
                    question_json["daily_double"] = game_question.daily_double

    game_json = game_data.dump(included_relations=[Game.game_contestants], id="game_id")

    database.save_game(game_data)

    return render_locale_template(
        "presenter/selection.html",
        game_data.pack.language,
        first_round=first_round,
        round_name=round_data.name,
        **game_json,
        **round_json,
    )

@presenter_page.route("/<game_id>/finale")
@_request_decorator
def finale(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    active_question = game_data.get_active_question().question
    question_json = active_question.dump(id="question_id")
    question_json["category"] = active_question.category.dump(included_relations=[])
    game_data.stage = StageType.FINALE_RESULT

    database.save_game(game_data)

    # Get game JSON data with nested contestant data
    game_json = game_data.dump(included_relations=[Game.game_contestants], id="game_id")
    locale_data = flask.current_app.config["LOCALES"].get(game_data.pack.language.value)
    page_locale = locale_data["pages"]["presenter/finale"]

    for contestant in game_json["game_contestants"]:
        wager = contestant["finale_wager"]
        contestant["wager"] = wager if wager > 0 else page_locale["nothing"]
        answer = contestant["finale_answer"]
        contestant["answer"] = page_locale["nothing"] if answer is None else f"'{answer}'"

    return render_locale_template(
        "presenter/finale.html",
        game_data.pack.language,
        media_sizes=Config.QUESTION_MEDIA_SIZES,
        **game_json,
        **question_json
    )

@presenter_page.route("/<game_id>/endscreen")
@_request_decorator
def endscreen(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]
    game_data.stage = StageType.ENDED

    database.save_game(game_data)

    locale_data = flask.current_app.config["LOCALES"].get(game_data.pack.language.value)
    page_locale = locale_data["pages"]["presenter/endscreen"]

    # Game over! Go to endscreen
    winners = game_data.get_game_winners()

    if len(winners) == 1: # Only one winner
        winner_desc = (
            f'<span style="color: {winners[0].contestant.color}; font-weight: 800;">'
            f"{winners[0].contestant.name}</span> {page_locale['winner_flavor_1']}"
        )

    elif len(winners) == 2: # Two winners tied in points
        winner_desc = (
            f'<span style="color: {winners[0].contestant.color}">{winners[0].contestant.name}</span> '
            f'{page_locale["and"]} <span style="color: {winners[1].contestant.color}; font-weight: 800;">{winners[1].contestant.name}</span> '
            f"{page_locale['winner_flavor_2']}"
        )

    else: # More than two winners tied in points
        players_tied = ", ".join(
            f'<span style="color: {data.contestant.color}; font-weight: 800;">{data.contestant.name}</span>' for data in winners[:-1]
        ) + f', {page_locale["and"]} <span style="color: {winners[-1].contestant.color}; font-weight: 800;">{winners[-1].contestant.name}</span>'

        winner_desc = (
            f"{players_tied} {page_locale['winner_flavor_3']}"
        )

    winners_json = [winner.dump() for winner in winners]
    logger.bind(event="jeopardy_player_data", player_data=winners_json).info(f"Jeopardy player data at endscreen: {winners_json}")

    game_json = game_data.dump(included_relations=[Game.game_contestants], id="game_id")
    game_json["game_contestants"].sort(key=lambda c: (-c["score"], c["contestant"]["name"]))

    # Send post request to Int-Far if LAN is active
    if _is_lan_active(game_data):
        print("Sending update to Int-Far")
        base_url = "http://localhost:5000" if "localhost" in flask.request.host else "https://mhooge.com"
        with open(f"{Config.STATIC_FOLDER}/secret.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)
            admin_id = data["intfar_disc_id"]
            token = data["intfar_user_id"]

        request_json = {"player_data": game_json["game_contestants"], "disc_id": admin_id, "token": token}
        try:
            response = requests.post(f"{base_url}/intfar/lan/jeopardy_winner", json=request_json, timeout=8)
            if response.status_code != 200:
                logger.bind(response=response.text, status=response.status_code).error(f"End of game request to Int-Far failed with status {response.status_code}")
        except (requests.RequestException, requests.Timeout):
            logger.exception("Failed sending end of game request to Int-Far!")

    return render_locale_template(
        "presenter/endscreen.html",
        game_data.pack.language,
        **game_json,
        winners=winners_json,
        winner_desc=winner_desc,
    )

@presenter_page.route("/<game_id>/cheatsheet")
@_request_decorator
def cheatsheet(game_data: Game):
    all_round_data = []
    for round_data in game_data.pack.rounds:
        round_json = round_data.dump()
        all_round_data.append(round_json)

    return render_locale_template("presenter/cheatsheet.html", rounds=all_round_data)
