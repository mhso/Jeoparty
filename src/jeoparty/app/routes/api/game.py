import random

import flask
from flask import json
from mhooge_flask.auth import get_user_details
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io, make_json_response
import requests

from jeoparty.api.database import Database
from jeoparty.api.config import Config
from jeoparty.api.enums import StageType
from jeoparty.api.orm.models import Game, GameContestant, GameQuestion
from jeoparty.app.routes.api.socket import GameSocketHandler, get_namespace_handler
from jeoparty.app.routes.api.shared import (
    get_question_answer_sounds,
    get_question_answer_images,
    get_contestant_id_from_cookie,
    is_lan_active,
)

game_page = flask.Blueprint("game_api", __name__, template_folder="templates")

def _get_intfar_request_params(config: Config):
    base_url = f"{config.internal_host_url}:5000"

    with open(f"{Config.STATIC_FOLDER}/secret.json", "r", encoding="utf-8") as fp:
        data = json.load(fp)
        admin_id = data["intfar_disc_id"]
        token = data["intfar_user_id"]

    request_json = {"disc_id": admin_id, "token": token}

    return base_url, request_json

def _get_lobby_state(game_data: Game):
    config: Config = flask.current_app.config["APP_CONFIG"]
    join_url = f"{config.external_host_url}/jeoparty/{game_data.join_code}"

    lan_mode = is_lan_active(game_data)
    if lan_mode:
        # Send host URL to Int-Far, if a LAN is active
        base_url, request_json = _get_intfar_request_params(config)

        request_json["join_url"] = join_url
        if game_data.password:
            request_json["password"] = game_data.password

        print(f"Sending info to Int-Far at '{base_url}': {request_json}")

        try:
            response = requests.post(f"{base_url}/intfar/lan/set_jeoparty_info", json=request_json, timeout=6)
            if response.status_code != 200:
                logger.bind(response=response.text, status=response.status_code).error(f"Start of game request to Int-Far failed with status {response.status_code}")
        except (requests.RequestException, requests.Timeout):
            logger.exception("Failed sending start of game request to Int-Far!")

    pack_json = game_data.pack.dump()


    return {
        "join_url": join_url,
        "lan_mode": lan_mode,
        "lobby_music": pack_json["lobby_music"],
        "lobby_volume": pack_json["lobby_volume"]
    }

def _get_question_state(game_data: Game, game_question: GameQuestion):
    """
    Returns the active question and the top-level media fields that go with it
    (answer images/sounds and media sizes) as two separate dicts.
    """
    question_json = game_question.question.dump()
    question_json["category"] = game_question.question.category.dump(included_relations=[])
    question_json["daily_double"] = game_question.daily_double

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_json["extra"]:
        random.shuffle(question_json["extra"]["choices"])

    # Get images and sounds for when questions are answered correctly/wrong
    correct_image, wrong_image = get_question_answer_images(game_data.pack.theme)
    correct_sound, wrong_sounds = get_question_answer_sounds(game_data.pack.theme, game_data.max_contestants)

    media_json = {
        "correct_image": correct_image,
        "wrong_image": wrong_image,
        "correct_sound": correct_sound,
        "wrong_sounds": wrong_sounds,
        "media_sizes": Config.QUESTION_MEDIA_SIZES,
    }

    return question_json, media_json

def _get_selection_state(game_data: Game):
    previous_question = game_data.get_active_question()
    questions = game_data.get_questions_for_round()

    start_of_round = questions != [] and not previous_question and not any(question.used for question in questions)
    start_of_game = start_of_round and game_data.round == 1 and game_data.get_contestant_with_turn() is None

    round_data = game_data.pack.rounds[game_data.round - 1]
    round_json = round_data.dump()
    del round_json["round"]

    # Merge data about game questions and actual questions
    for category_json in round_json["categories"]:
        for question_json in category_json["questions"]:
            for game_question in questions:
                if game_question.question_id == question_json["id"]:
                    question_json["active"] = game_question.active
                    question_json["used"] = game_question.used
                    question_json["daily_double"] = game_question.daily_double

    return round_json, start_of_game

def _get_endscreen_state(game_data: Game):
    winners = game_data.get_game_winners()

    return [
        {
            "id": winner.id,
            "name": winner.contestant.name,
            "color": winner.contestant.color,
            "avatar": winner.contestant.avatar,
        }
        for winner in winners
    ]

def _get_game_state(game_data: Game):
    # Shared data cross stages
    game_json = game_data.dump(included_relations=[])

    # Get nested game contestant data
    game_contestants = []
    for game_contestant in game_data.game_contestants:
        game_contestants.append(game_contestant.dump(included_relations=[GameContestant.power_ups]))

    game_json["game_contestants"] = game_contestants

    theme = game_data.pack.theme
    round_name = game_data.pack.rounds[game_data.round - 1].name

    state_json = {
        "game": game_json,
        "theme": theme.dump() if theme else None,
        "round_name": round_name,
        "language": game_data.pack.language.value,
    }

    if game_data.stage is StageType.LOBBY:
        state_json["lobby_info"] = _get_lobby_state(game_data)

    elif game_data.stage in (StageType.QUESTION, StageType.FINALE_QUESTION):
        game_question: GameQuestion | None = game_data.get_active_question()
        if game_question is None or game_question.used:
            # If question does not exist or has already been answered, return error
            return make_json_response("Question was not found or has already been asked.", 400)

        state_json["question"], media_json = _get_question_state(game_data, game_question)
        state_json.update(media_json)

    elif game_data.stage is (StageType.SELECTION, StageType.FINALE_WAGER):
        round_data, start_of_game = _get_selection_state(game_data)
        state_json["round"] = round_data
        state_json["start_of_game"] = start_of_game

    elif game_data.stage is StageType.ENDED:
        state_json["winners"] = _get_endscreen_state(game_data)

    return make_json_response(state_json, 200)

@game_page.route("/game/<game_id>/presenter-state")
def get_presenter_state(game_id: str):
    database: Database = flask.current_app.config["DATABASE"]
    with database:
        # Ensure user is logged in
        if (user_details := get_user_details()) is None:
            return make_json_response("You are not authorized, please log in first.", 401)

        # Retrieve the game data for the given game ID or abort if it is missing
        game_data = database.get_game_from_id(game_id)
        if game_data is None:
            return make_json_response("A game with the given ID was not found.", 404)

        # Verify the user actually created the game
        if user_details[0] != game_data.created_by:
            return make_json_response("You are not the creator of the given game.", 401)

        # Setup socket namespace for the given game
        namespace_handler = get_namespace_handler(game_id)

        if namespace_handler is None:
            namespace_handler = GameSocketHandler(game_data.id, database)
            socket_io.on_namespace(namespace_handler)

        return _get_game_state(game_data)

def _transition_question(database: Database, game_data: Game):
    # Set stage to 'question' or 'finale_question'
    game_data.stage = StageType.FINALE_QUESTION if game_data.stage == StageType.FINALE_WAGER else StageType.QUESTION

    # Disable all power-ups except hijack unless question is daily double or we are at the finale
    for contestant in game_data.game_contestants:
        for power_up in contestant.power_ups:
            power_up.enabled = False

        database.save_models(*contestant.power_ups)

def _transition_selection(database: Database, game_data: Game):
    """
    Transition the game to the 'selection' stage where contestants
    can pick a category for the next question stage.
    """
    # Get currently active question (if any) and mark it as inactive and used
    previous_question = game_data.get_active_question()
    if previous_question:
        previous_question.used = True
        previous_question.active = False
        database.save_models(previous_question)

    # Set game stage to 'selection'
    stage = StageType.SELECTION

    # Check if we are done with all questions in the current round
    questions = game_data.get_questions_for_round()
    start_of_round = questions != [] and not previous_question and not any(question.used for question in questions)
    end_of_round = questions != [] and all(question.used for question in questions)

    is_finale = False
    if end_of_round:
        # Round done, onwards to the next one!
        game_data.round += 1

        if game_data.round > game_data.regular_rounds:
            if not game_data.pack.include_finale:
                stage = StageType.ENDED

            else:
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
            stage = StageType.FINALE_WAGER
            if game_data.round < len(game_data.pack.rounds):
                # If the game has less rounds than the question pack
                # and this round is the finale, set the round to equal
                # the last round of the pack
                game_data.round = len(game_data.pack.rounds)

        questions = game_data.get_questions_for_round()

    if is_finale:
        # Set the single finale question as the active question
        questions[0].active = True

    game_data.stage = stage

    if (start_of_round or end_of_round) and not is_finale:
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

def _transition_endscreen(game_data: Game):
    config: Config = flask.current_app.config["APP_CONFIG"]

    game_data.stage = StageType.ENDED

    winners = game_data.get_game_winners()
    winners_json = [winner.dump() for winner in winners]
    logger.bind(event="jeopardy_player_data", player_data=winners_json).info(f"Jeopardy player data at endscreen: {winners_json}")

    game_json = game_data.dump(included_relations=[Game.game_contestants], id="game_id")
    game_json["game_contestants"].sort(key=lambda c: (-c["score"], c["contestant"]["name"]))

    # Send post request to Int-Far if LAN is active
    if is_lan_active(game_data):
        print("Sending update to Int-Far")
        base_url, request_json = _get_intfar_request_params(config)

        request_json["player_data"] = game_json["game_contestants"]

        try:
            response = requests.post(f"{base_url}/intfar/lan/jeopardy_winner", json=request_json, timeout=8)
            if response.status_code != 200:
                logger.bind(response=response.text, status=response.status_code).error(f"End of game request to Int-Far failed with status {response.status_code}")
        except (requests.RequestException, requests.Timeout):
            logger.exception("Failed sending end of game request to Int-Far!")

@game_page.route("/game/<game_id>/advance/<target>", methods=["POST"])
def transition_state(game_id: str, target: str):
    target_stage = StageType(target)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        # Ensure user is logged in
        if (user_details := get_user_details()) is None:
            return make_json_response("You are not authorized, please log in first.", 401)

        # Retrieve the game data for the given game ID or abort if it is missing
        game_data = database.get_game_from_id(game_id)
        if game_data is None:
            return make_json_response("A game with the given ID was not found.", 404)

        # Verify the user actually created the game
        if user_details[0] != game_data.created_by:
            return make_json_response("You are not the creator of the given game.", 401)

        if target_stage is StageType.QUESTION:
            _transition_question(database, game_data)

        elif target_stage is StageType.SELECTION:
            _transition_selection(database, game_data)

        elif target_stage is StageType.FINALE_RESULT:
            game_data.stage = StageType.FINALE_RESULT

        elif target_stage is StageType.ENDED:
            _transition_endscreen(game_data)

        database.save_game(game_data)
        if (handler := get_namespace_handler(game_id)) is not None:
            handler.invalidate_game_data()

        return _get_game_state(game_data)

@game_page.route("/game/<game_id>/contestant-state")
def get_contestant_state(game_id: str):
    user_id = get_contestant_id_from_cookie(flask.request.cookies)

    database: Database = flask.current_app.config["DATABASE"]

    with database:
        # Validate that user_id is saved as a cookie
        if user_id is None:
            return make_json_response("You are not authorized to access this.", 401)

        game_data = database.get_game_from_id(game_id)
        if game_data is None:
            return make_json_response("No game with the given ID exists.", 404)

        # Find the game contestant matching the given user_id
        contestant_data = game_data.get_contestant(contestant_id=user_id)

        if contestant_data is None: # User haven't joined the game yet
            return make_json_response("You are not a contestant in this game.", 403)

        # Get question data
        game_question = game_data.get_active_question()
        if game_question is not None:
            question_json_full = game_question.question.dump() 
    
            # Select only required category fields
            category_keys_to_include = ["id", "name"]
            category_json_full = game_question.question.category.dump(included_relations=[])
            question_json_full["category"] = {key: category_json_full[key] for key in category_keys_to_include}

            question_json_full["daily_double"] = game_question.daily_double

            if game_data.stage is StageType.FINALE_QUESTION:
                question_json_full["question"] = game_question.question

        else:
            question_json_full = None

        round_name = game_data.pack.rounds[game_data.round - 1].name

        questions = game_data.get_questions_for_round()
        start_of_round = questions != [] and not game_data.get_active_question() and not any(question.used for question in questions)
        start_of_game = start_of_round and game_data.round == 1 and game_data.get_contestant_with_turn() is None

        game_json_full = game_data.dump(included_relations=[])

        # Select only required player_with_turn fields
        turn_player_fields_to_include = ["id", "name", "color"]
        if game_json_full["player_with_turn"]:
            player_with_turn = {key: game_json_full["player_with_turn"][key] for key in turn_player_fields_to_include}
        else:
            player_with_turn = None

        # Select only required game data fields
        game_keys_to_include = ["id", "stage", "round", "total_rounds", "question_num", "max_value", "title"]
        game_json = {key: game_json_full[key] for key in game_keys_to_include}

        # Select only required question fields
        question_keys_to_include = ["id", "value", "daily_double", "category"]
        if question_json_full is not None:
            questions_json = {key: question_json_full[key] for key in question_keys_to_include}
        else:
            questions_json = None

        num_questions_in_round = len(questions)

        json_data = {
            "game": game_json,
            "me": contestant_data.dump(),
            "question": questions_json,
            "player_with_turn": player_with_turn,
            "num_questions_in_round": num_questions_in_round,
            "round_name": round_name,
            "language": game_data.pack.language.value,
            "start_of_game": start_of_game,
        }

        # If game is ended, save whether this contestant won
        if game_data.stage == StageType.ENDED:
            winners = game_data.get_game_winners()
            contestant_won = False
            for winner_data in winners:
                if winner_data.id == contestant_data.id:
                    contestant_won = True

            json_data["winner"] = contestant_won

        return make_json_response(json_data, 200)
