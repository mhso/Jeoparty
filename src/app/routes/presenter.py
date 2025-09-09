import json
import os
import random

import flask
from mhooge_flask.auth import get_user_details
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io, make_template_context

from api.database import Database
from api.config import Config
from api.enums import PowerUpType, StageType
from api.orm.models import Game, GameQuestion, GamePowerUp
from app.routes.socket import GameSocketHandler
from app.routes.shared import  redirect_to_login, get_data_path_for_question_pack

presenter_page = flask.Blueprint("presenter", __name__, template_folder="templates")

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
        game_namespace = f"{game_id}/"
        if socket_io.server:
            namespaces = socket_io.server.namespace_handlers
        else:
            namespaces = socket_io.namespace_handlers

        registered = False
        for namespace in namespaces:
            if namespace == game_namespace:
                registered = True
                break

        database: Database = flask.current_app.config["DATABASE"]
        with database:
            # Ensure user is logged in or redirect to login
            if get_user_details() is None:
                return redirect_to_login(f"presenter.{func.__name__}", game_id=game_id)
    
            # Retrieve the game data for the given game ID or abort if it is missing
            game_data = database.get_game_from_id(game_id)
            if game_data is None:
                return flask.abort(404)

            if not registered:
                socket_io.on_namespace(GameSocketHandler(game_namespace, game_data))

            # Inject game data to the route handler
            return func(game_data=game_data, *args, **kwargs)

    wrapper.__setattr__("__name__", func.__name__)

    return wrapper

@presenter_page.route("/<game_id>")
@_request_decorator
def lobby(game_data: Game):
    join_url = f"mhooge.com/jeoparty/{game_data.join_code}"

    data_path = get_data_path_for_question_pack(game_data.pack_id, False)
    if os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "lobby_music.mp3")):
        lobby_music_path = os.path.join(data_path, "lobby_music.mp3")
    else:
        lobby_music_path = None

    game_data.json["game_id"] = game_data.json["id"]
    del game_data.json["id"]

    lan_mode = (
        game_data.pack.name.startswith("LoL Jeopardy")
        and game_data.created_by == Config.ADMIN_ID
        and False
    )

    return make_template_context(
        "presenter/lobby.html",
        join_url=join_url,
        lan_mode=lan_mode,
        lobby_music=lobby_music_path,
        **game_data.json,
    )

def _get_question_answer_sounds(game_data: Game):
    correct_sounds = [
        os.path.join(get_data_path_for_question_pack(game_data.pack_id, sound))
        for sound in game_data.pack.buzzer_sounds if sound.correct
    ]

    if correct_sounds == []:
        # Get default correct answer sound
        correct_sound = "data/sounds/correct_answer.mp3"
    else:
        correct_sound = random.choice(correct_sounds)

    wrong_sounds = [
        os.path.join(get_data_path_for_question_pack(game_data.pack_id, sound))
        for sound in game_data.pack.buzzer_sounds if not sound.correct
    ]

    # Get as many wrong sounds as there are contestants, adding in default sounds
    # if we don't have enough custom ones
    if len(wrong_sounds) < game_data.max_contestants:
        # Add default wrong answer sound
        wrong_sounds = wrong_sounds + ["data/sounds/wrong_answer.mp3" for _ in range(game_data.max_contestants - len(wrong_sounds))]

    random.shuffle(wrong_sounds)
    wrong_sounds = wrong_sounds[:game_data.max_contestants]

    return correct_sound, wrong_sounds

@presenter_page.route("<game_id>/question")
@_request_decorator
def question(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    game_question: GameQuestion | None = game_data.get_active_question()
    if game_question is None or game_question.used:
        # If question does not exist or has already been answered, redirect back to selection
        return flask.redirect(flask.url_for(".selection", game_id=game_data.id))

    is_daily_double = game_data.use_daily_doubles and game_question.daily_double
    question_data = game_question.question
    question_data.json["daily_double"] = game_question.daily_double

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_data.extra:
        random.shuffle(question_data.json["extra"]["choices"])

    # Set stage to 'question' or 'finale_question'
    game_data.stage = StageType.FINALE_QUESTION if game_data.stage == StageType.FINALE_WAGER else StageType.QUESTION

    # Disable all power-ups except hijack unless question is daily double or we are at the finale
    for contestant in game_data.game_contestants:
        for power_up in contestant.power_ups:
            power_up.enabled = (
                power_up.power_up.type is PowerUpType.HIJACK
                and not is_daily_double
                and game_data.stage is not StageType.FINALE_QUESTION
            )

    database.save_game(game_data)

    # Get random sounds that plays for correct/wrong answers
    correct_sound, wrong_sounds = _get_question_answer_sounds(game_data)
    power_ups = [power.value for power in PowerUpType]

    # Get videos that play when a power-up is used

    # Make sure no dictionary keys conflict
    game_data.json["game_id"] = game_data.json["id"]
    del game_data.json["id"]

    question_data.json["question_id"] = question_data.json["id"]
    del question_data.json["id"]

    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

    return make_template_context(
        "presenter/question.html",
        base_folder=get_data_path_for_question_pack(game_data.pack_id, False),
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        power_ups=power_ups,
        daily_double=is_daily_double,
        **game_data.json,
        **question_data.json,
    )

@presenter_page.route("<game_id>/selection")
@_request_decorator
def selection(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    # Get currently active question (if any) and mark it as inactive and used
    previous_question = game_data.get_active_question()
    if previous_question:
        previous_question.used = True
        previous_question.active = False
        database.save_game_question(previous_question)

    # Set game stage to 'selection'
    game_data.stage = StageType.SELECTION

    # Check if we are done with all questions in the current round
    questions = game_data.get_questions_for_round()
    end_of_round = all(question.used for question in questions)

    is_finale = False
    if end_of_round:
        # Round done, onwards to the next one!
        game_data.round += 1

        if game_data.round > game_data.regular_rounds + 1:
            if not game_data.pack.include_finale:
                # No finale, so game is over. Redirect directly to endscreen
                return flask.redirect(flask.url_for(".endscreen", game_id=game_data.id))

            is_finale = True
        else:
            # The player with the lowest score at the start of a new regular round gets the turn
            lowest_score = 0
            lowers_score_id = game_data.game_contestants[0].contestant_id
            for contestant in game_data.game_contestants:
                if contestant.score < lowest_score:
                    lowers_score_id = contestant.contestant_id
                    lowest_score = contestant.score

            game_data.set_contestant_turn(lowers_score_id)

        if is_finale:
            game_data.stage = StageType.FINALE_WAGER

    game_questions = game_data.get_questions_for_round()
    if is_finale:
        # Set the single finale question as the active question
        game_questions[0].active = True

    first_round = False
    if not previous_question or end_of_round and not is_finale and game_data.use_daily_doubles:
        # If it's the first question of a new round, select random questions to be daily doubles
        first_round = game_data.get_contestant_with_turn() is None
        questions_copy = list(game_questions)
        random.shuffle(questions_copy)

        for game_question in questions_copy[:game_data.round + 1]:
            game_question.daily_double = True

    # TODO: Handle case where there are not enough questions for the given round
    round_data = game_data.pack.rounds[game_data.round]
    game_questions = game_data.get_questions_for_round()
    for category in round_data.json["categories"]:
        for question in category["questions"]:
            for game_question in game_questions:
                if game_question.question_id == question["id"]:
                    question["active"] = game_question.active
                    question["used"] = game_question.used
                    question["daily_double"] = game_question.daily_double

    # Reset used power-ups
    for contestant in game_data.game_contestants:
        contestant.power_ups = [
            GamePowerUp(
                game_id=game_data.id,
                contestant_id=contestant.id,
                power_id=power_up.id,
                type=power_up.type
            )
            for power_up in game_data.pack.power_ups
        ]

    # Make sure no dictionary keys conflict
    game_data.json["game_id"] = game_data.json["id"]
    del game_data.json["id"]

    round_data.json["round_id"] = round_data.json["id"]
    del round_data.json["id"]

    database.save_game(game_data)
    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

    return make_template_context(
        "presenter/selection.html",
        first_round=first_round,
        **game_data.json,
        **round_data.json,
    )

@presenter_page.route("<game_id>/finale")
@_request_decorator
def finale(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    game_question = game_data.get_active_question().question
    game_data.stage = StageType.FINALE_RESULT

    database.save_game(game_data)

    for contestant in game_data.game_contestants:
        wager = contestant.finale_wager
        contestant.json["wager"] = wager if wager > 0 else "nothing"
        answer = contestant.finale_answer
        contestant.json["answer"] = "nothing" if answer is None else f"'{answer}'"

    game_data.json["game_id"] = game_data.json["id"]
    del game_data.json["id"]

    game_question.json["question_id"] = game_question.json["id"]
    del game_question.json["id"]

    return make_template_context(
        "jeopardy/presenter_finale.html",
        **game_data.json,
        **game_question.json
    )

@presenter_page.route("<game_id>/endscreen")
@_request_decorator
def endscreen(game_data: Game):
    # Game over! Go to endscreen
    winners = game_data.get_game_winners()

    if len(winners) == 1:
        winner_desc = f'<span style="color: #{winners[0].contestant.color}; font-weight: 800;">{winners[0].contestant.name}</span> wonnered!!! All hail the king!'

    elif len(winners) == 2:
        winner_desc = (
            f'<span style="color: #{winners[0].contestant.color}">{winners[0].contestant.name}</span> '
            f'and <span style="color: #{winners[1].contestant.color}; font-weight: 800;">{winners[1].contestant.name}</span> '
            "have the same amount of points, they both win!!!"
        )

    else:
        players_tied = ", ".join(
            f'<span style="color: #{data.contestant.color}; font-weight: 800;">{data.contestant.name}</span>' for data in winners
        ) + f', and <span style="color: #{winners[-1].contestant.color}; font-weight: 800;">{winners[-1].contestant.name}</span>'

        winner_desc = (
            f"{players_tied} all have equal amount of points! They are all winners!!!"
        )

    winners_json = [winner.json for winner in winners]
    logger.bind(event="jeopardy_player_data", player_data=winners_json).info(f"Jeopardy player data at endscreen: {winners_json}")

    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

    return make_template_context(
        "jeopardy/presenter_endscreen.html",
        **game_data.json,
        winners=winners_json,
        winner_desc=winner_desc,
    )

@presenter_page.route("<game_id>/cheatsheet")
def cheatsheet():
    if get_user_details() is None:
        return redirect_to_login("presenter.cheatsheet")

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    return make_template_context("presenter/cheat_sheet.html", questions=questions)
