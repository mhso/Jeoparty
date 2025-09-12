import json
import os
import random

import flask
from mhooge_flask.auth import get_user_details
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io

from api.database import Database
from api.config import Config
from api.enums import PowerUpType, StageType
from api.orm.models import Game, GameQuestion
from app.routes.socket import GameSocketHandler
from app.routes.shared import  redirect_to_login, get_data_path_for_question_pack, render_locale_template

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
        if socket_io.server:
            namespaces = socket_io.server.namespace_handlers
        else:
            namespaces = socket_io.namespace_handlers

        registered = False
        for namespace in namespaces:
            if namespace == f"/{game_id}":
                registered = True
                break

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

            if not registered:
                socket_io.on_namespace(GameSocketHandler(game_data.id))

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
        lobby_music_path = f"{data_path}/lobby_music.mp3"
    else:
        lobby_music_path = None

    # Get game JSON data with nested contestant data
    game_json = _dump_game_to_json(game_data)
    game_json["stage"] = "LOBBY"

    lan_mode = (
        game_data.pack.name.startswith("LoL Jeopardy")
        and game_data.created_by == Config.ADMIN_ID
        and False
    )

    return render_locale_template(
        "presenter/lobby.html",
        game_data.pack.language,
        join_url=join_url,
        lan_mode=lan_mode,
        lobby_music=lobby_music_path,
        **game_json,
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

def _dump_game_to_json(game_data: Game):
    game_json = game_data.dump(id="game_id")
    game_json["game_contestants"] = []

    # Handle contestants and their power-ups
    for contestant_data in game_data.game_contestants:
        contestant_json = contestant_data.dump()
        del contestant_json["game"]
        game_json["game_contestants"].append(contestant_json)

    return game_json

@presenter_page.route("/<game_id>/question")
@_request_decorator
def question(game_data: Game):
    database: Database = flask.current_app.config["DATABASE"]

    game_question: GameQuestion | None = game_data.get_active_question()
    if game_question is None or game_question.used:
        # If question does not exist or has already been answered, redirect back to selection
        return flask.redirect(flask.url_for(".selection", game_id=game_data.id))

    is_daily_double = game_data.use_daily_doubles and game_question.daily_double
    question_json = game_question.question.dump(id="question_id")
    question_json["daily_double"] = game_question.daily_double
    del question_json["game_questions"]

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_json["extra"]:
        random.shuffle(question_json["extra"]["choices"])

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

        database.save_models(*contestant.power_ups)

    database.save_game(game_data)

    round_name = game_data.pack.rounds[game_data.round - 1].name

    # Get images for when questiton is answered correctly or wrong
    data_path = get_data_path_for_question_pack(game_data.pack_id, False)
    if os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "correct_answer.png")):
        correct_image = f"{data_path}/correct_answer.png"
    else:
        correct_image = "img/check.png"

    if os.path.exists(os.path.join(Config.STATIC_FOLDER, data_path, "wrong_answer.png")):
        wrong_image = f"{data_path}/wrong_answer.png"
    else:
        wrong_image = "img/error.png"

    # Get random sounds that plays for correct/wrong answers
    correct_sound, wrong_sounds = _get_question_answer_sounds(game_data)
    power_ups = [power.value for power in PowerUpType]

    # Get game JSON data with nested contestant data
    game_json = _dump_game_to_json(game_data)

    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

    return render_locale_template(
        "presenter/question.html",
        game_data.pack.language,
        base_folder=f"{get_data_path_for_question_pack(game_data.pack_id, False)}/",
        correct_image=correct_image,
        wrong_image=wrong_image,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        power_ups=power_ups,
        round_name=round_name,
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

        if game_data.round > game_data.regular_rounds:
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

    first_round = not previous_question and game_data.round == 1 and game_data.get_contestant_with_turn() is None
    if not previous_question or end_of_round and not is_finale and game_data.use_daily_doubles:
        # If it's the first question of a new round, select random questions to be daily doubles
        questions_copy = list(game_questions)
        random.shuffle(questions_copy)

        for index, game_question in enumerate(questions_copy):
            game_question.daily_double = index < game_data.round

        database.save_models(*questions_copy)

        # Reset used power-ups
        for contestant in game_data.game_contestants:
            for power_up in contestant.power_ups:
                power_up.used = False

            database.save_models(*contestant.power_ups)

    # TODO: Handle case where there are not enough questions for the given round
    round_data = game_data.pack.rounds[game_data.round - 1]
    round_json = round_data.dump(id="round_id")
    del round_json["pack"]
    del round_json["round"]
    round_json["categories"] = []

    game_questions = game_data.get_questions_for_round()
    for category in round_data.categories:
        category_json = category.dump(id="category_id")
        category_json["questions"] = []

        for question in category.questions:
            question_json = question.dump(id="question_id")

            for game_question in game_questions:
                if game_question.question_id == question.id:
                    question_json["active"] = game_question.active
                    question_json["used"] = game_question.used
                    question_json["daily_double"] = game_question.daily_double

            category_json["questions"].append(question_json)

        round_json["categories"].append(category_json)

    # Get game JSON data with nested contestant data
    game_json = _dump_game_to_json(game_data)

    database.save_game(game_data)
    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

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

    question_json = game_data.get_active_question().question.dump(id="question_id")
    game_data.stage = StageType.FINALE_RESULT

    database.save_game(game_data)

    # Get game JSON data with nested contestant data
    game_json = _dump_game_to_json(game_data)

    for contestant in game_json["game_contestants"]:
        wager = contestant.finale_wager
        contestant["wager"] = wager if wager > 0 else "nothing"
        answer = contestant.finale_answer
        contestant["answer"] = "nothing" if answer is None else f"'{answer}'"

    return render_locale_template(
        "jeopardy/presenter_finale.html",
        game_data.pack.language,
        **game_data,
        **question_json
    )

@presenter_page.route("/<game_id>/endscreen")
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

    winners_json = [winner.dump() for winner in winners]
    logger.bind(event="jeopardy_player_data", player_data=winners_json).info(f"Jeopardy player data at endscreen: {winners_json}")

    socket_io.emit("state_changed", to="contestants", namespace=f"/{game_data.id}")

    return render_locale_template(
        "jeopardy/presenter_endscreen.html",
        game_data.pack.language,
        **_dump_game_to_json(game_data),
        winners=winners_json,
        winner_desc=winner_desc,
    )

@presenter_page.route("/<game_id>/cheatsheet")
def cheatsheet():
    if get_user_details() is None:
        return redirect_to_login("presenter.cheatsheet")

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    return render_locale_template("presenter/cheat_sheet.html", questions=questions)
