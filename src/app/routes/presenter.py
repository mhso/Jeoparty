import json
import os
import random
from time import time
from dataclasses import dataclass, field
from typing import Dict, List
from gevent import sleep

import flask
from flask_socketio import join_room, leave_room, emit
from mhooge_flask.auth import get_user_details
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io, make_template_context, make_text_response

from api.database import Database
from api.config import STATIC_FOLDER
from api.enums import PowerUp, Stage
from api.orm.models import GameQuestion
from app.routes.shared import ContestantMetadata, redirect_to_login, get_data_path_for_question_pack, get_contestant_metadata
from api.util import JEOPARDY_ITERATION, JEOPADY_EDITION, JEOPARDY_REGULAR_ROUNDS, MONTH_NAMES
from api.lan import is_lan_ongoing, get_latest_lan_info

TRACK_UNUSED = True
DO_DAILY_DOUBLE = True

QUESTIONS_PER_ROUND = 30
# Round when Final Jeopardy is played
FINALE_ROUND = JEOPARDY_REGULAR_ROUNDS + 1
ROUND_NAMES = ["Jeopardy!"] + (["Double Jeopardy!"] * (JEOPARDY_REGULAR_ROUNDS - 1)) + ["Final Jeopardy!"]

FINALE_CATEGORY = "history"

QUESTIONS_FILE = f"app/static/data/jeopardy_questions_{JEOPARDY_ITERATION}.json"
USED_QUESTIONS_FILE = f"app/static/data/jeopardy_used_{JEOPARDY_ITERATION}.json"

PLAYER_NAMES = {
    115142485579137029: "Dave",
    172757468814770176: "Murt",
    331082926475182081: "Muds",
    219497453374668815: "Tommy"
}

PLAYER_INDEXES = list(PLAYER_NAMES.keys())

PLAYER_BACKGROUNDS = {
    115142485579137029: "coven_nami.png",
    172757468814770176: "pentakill_olaf.png", 
    331082926475182081: "crime_city_tf.png",
    219497453374668815: "bard_splash.png"
}

# Sounds for answering questions correctly/wrong.
ANSWER_SOUNDS = [
    [
        "easy_money",
        "how_lovely",
        "outta_my_face",
        "yeah",
        "heyheyhey",
        "peanut",
        "never_surrender",
        "exactly",
        "hell_yeah",
        "ult",
        "wheeze",
        "demon",
        "myoo",
        "rimelig_stor",
        "worst_laugh",
        "nyong",
        "climax",
        "cackle",
        "kabim",
        "kvinder",
        "uhu",
        "porn",
        "package_boy",
        "skorpion",
        "goblin",
        "ngh",
    ],
    [
        "mmnonono",
        "what",
        "whatemagonodo",
        "yoda",
        "daisy",
        "bass",
        "despair",
        "ahhh",
        "spil",
        "fedtmand",
        "no_way",
        "hehehe",
        "braindead",
        "big_nej",
        "junge",
        "sad_animal",
        "hold_da_op",
        "daser",
        "oh_no",
        "i_dont_know_dude",
        "disappoint",
        "nej",
        "wilhelm",
        "migjuana",
        "ah_nej",
        "dave_angy",
    ]
]

# Sounds played when a specific player buzzes in first
BUZZ_IN_SOUNDS = {
    115142485579137029: "buzz_dave",
    172757468814770176: "buzz_murt",
    331082926475182081: "buzz_muds",
    219497453374668815: "buzz_thommy",
}

@dataclass
class GameMetadata:
    question_asked_time: float | None = field(default=None, init=False)
    buzz_winner_decided: bool = field(default=False, init=False)
    power_use_decided: bool = field(default=False, init=False)

def _get_game_metadata(config, game_id: str):
    data = config["GAME_METADATA"].get(game_id)
    if data is None:
        data = GameMetadata()
        config["GAME_METADATA"][game_id] = data

    return data

presenter_page = flask.Blueprint("presenter", __name__, template_folder="templates")

@presenter_page.route("/<game_id>")
def lobby(game_id: str):
    if get_user_details() is None:
        return redirect_to_login("presenter.lobby", game_id=game_id)

    database: Database = flask.current_app.config["DATABASE"]

    game_data = database.get_game_from_id(game_id)

    if game_data is None:
        return flask.abort(404)

    join_url = f"https://mhooge.com/jeoparty/{game_id}"

    data_path = get_data_path_for_question_pack(game_data.pack_id, False)
    if os.path.exists(os.path.join(STATIC_FOLDER, data_path, "lobby_music.mp3")):
        lobby_music_path = os.path.join(data_path, "lobby_music.mp3")
    else:
        lobby_music_path = None

    return make_template_context(
        "jeopardy/presenter_lobby.html",
        **game_data.json,
        join_url=join_url,
        lobby_music=lobby_music_path
    )

@presenter_page.route("/reset_questions", methods=["POST"])
def reset_questions():
    if get_user_details() is None:
        return flask.abort(404)

    with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    for cat in used_questions:
        used_questions[cat] = [
            {"active": True, "used": [], "double": False}
            for _ in range(5)
        ]

    with open(USED_QUESTIONS_FILE, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

    return make_text_response("Questions reset", 200)

def get_round_data(request_args):
    player_data = []
    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

    for index in range(1, 5):
        id_key = f"i{index}"
        name_key = f"n{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if id_key in request_args:
            disc_id =  int(request_args[id_key])
            buzzes = 0
            hits = 0
            misses = 0
            finale_wager = 0
            score = int(request_args.get(score_key, 0))
            power_ups = []

            # Args from URL
            name = request_args[name_key]
            turn_id = PLAYER_INDEXES.index(disc_id)
            color = request_args[color_key]

            if disc_id in contestants:
                avatar = contestants[disc_id].avatar
                buzzes = contestants[disc_id].buzzes
                hits = contestants[disc_id].hits
                misses = contestants[disc_id].misses
                finale_wager = contestants[disc_id].finale_wager

                if contestants[disc_id].score != score:
                    contestants[disc_id].score = score

                power_ups = contestants[disc_id].power_ups
            else:
                avatar = flask.url_for("static", _external=True, filename="img/questionmark.png")

            player_data.append({
                "disc_id": str(disc_id),
                "name": name,
                "index": turn_id,
                "avatar": avatar,
                "score": score,
                "buzzes": buzzes,
                "hits": hits,
                "misses": misses,
                "finale_wager": finale_wager,
                "color": color,
                "power_ups": [power_up.__dict__ for power_up in power_ups],
            })

    try:
        player_turn = int(request_args["turn"])
    except ValueError:
        player_turn = -1

    try:
        question_num = int(request_args["question"])
    except ValueError:
        question_num = 0

    return player_data, player_turn, question_num

@presenter_page.route("<game_id>/question")
def question(game_id: str):
    if get_user_details() is None:
        return redirect_to_login("presenter.question", game_id=game_id)

    database: Database = flask.current_app.config["DATABASE"]
    game_data = database.get_game_from_id(game_id)
    if game_data is None:
        return flask.abort(404)

    jeopardy_round = game_data.round

    game_question: GameQuestion = game_data.get_active_question()
    if game_question is None or game_question.used:
        # If question does not exist or has already been answered, redirect back to selection
        return flask.redirect(flask.url_for(".selection", game_id=game_id))

    # Store a GameMetadata object in memory, to be used when
    # deciding who buzzed in first among other things
    _get_game_metadata(flask.current_app.config, game_id)

    is_daily_double = game_data.use_daily_doubles and game_question.daily_double

    question_data = game_question.question

    # If question is multiple-choice, randomize order of choices
    if "choices" in question_data.extra:
        random.shuffle(question_data.json["extra"]["choices"])

    # Disable all power-ups except hijack unless question is daily double
    for power_up in game_data.power_ups:
        power_up.enabled = power_up.power_up is PowerUp.HIJACK and not is_daily_double

    database.save_game(game_data)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        # Get player names and scores from query parameters
        player_data, player_turn, question_num = get_round_data(flask.request.args)
        contestants: Dict[int, Contestant] = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
        _sync_contestants(player_data, contestants)

        # Disable hijack if question is daily double
        for contestant in contestants.values():
            for power_up in contestant.power_ups:
                power_up.enabled = power_up.power_id == "hijack" and not is_daily_double

        question_state = QuestionState(
            jeopardy_round,
            ROUND_NAMES[jeopardy_round - 1],
            player_data,
            question_num,
            player_turn,
            questions[category]["name"],
            questions[category]["background"],
            question,
            questions[category]["tiers"][tier]["value"] * jeopardy_round,
            buzz_time,
            is_daily_double
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = question_state

        # Get random sounds that plays for correct/wrong answers
        correct_sound = random.choice(ANSWER_SOUNDS[0])
        possible_wrong_sounds = list(ANSWER_SOUNDS[1])
        random.shuffle(possible_wrong_sounds)
        wrong_sounds = possible_wrong_sounds[:4]

        socket_io.emit("state_changed", to="contestants")

    return make_template_context(
        "jeopardy/presenter_question.html",
        buzz_sounds=BUZZ_IN_SOUNDS,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        power_ups=POWER_UP_IDS,
        **question_state.__dict__
    )

@presenter_page.route("/selection/<jeopardy_round>")
def selection(jeopardy_round):
    if get_user_details() is None:
        return redirect_to_login("presenter.selection", jeopardy_round=jeopardy_round)

    # Get currently active question (if any) and mark it as inactive and used
    game_question.used = True
    database.save_game_question(game_question)

    jeopardy_round = int(jeopardy_round)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        # Get player names and scores from query parameters
        player_data, player_turn, question_num = get_round_data(flask.request.args)
        contestants: Dict[int, Contestant] = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
        _sync_contestants(player_data, contestants)

        if question_num == QUESTIONS_PER_ROUND:
            # Round done, onwards to next one
            jeopardy_round += 1
            question_num = 0

            if 1 < jeopardy_round < FINALE_ROUND:
                # The player with the lowest score at the start of a new regular round gets the turn
                lowest_score = player_data[0]["score"]
                lowers_score_index = 0

                for index, data in enumerate(player_data):
                    if data["score"] < lowest_score:
                        lowest_score = data["score"]
                        lowers_score_index = index

                player_turn = lowers_score_index

        with open(QUESTIONS_FILE, encoding="utf-8") as fp:
            questions = json.load(fp)

        with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
            used_questions = json.load(fp)

        if jeopardy_round == FINALE_ROUND:
            ordered_categories = ["history"]
        else:
            ordered_categories = [None] * 6
            for category in questions:
                if questions[category]["order"] < 6:
                    ordered_categories[questions[category]["order"]] = category

            if question_num == 0:
                # If it's the first question of a round, set all categories to active and reset daily doubles
                for category in used_questions:
                    for tier_info in used_questions[category]:
                        tier_info["active"] = True
                        tier_info["double"] = False

                # Reset used power-ups
                for data in player_data:
                    contestant = contestants[int(data["disc_id"])]
                    fresh_power_ups = _init_powerups()
                    contestant.power_ups = fresh_power_ups
                    data["power_ups"] = [power_up.__dict__ for power_up in fresh_power_ups]

                if DO_DAILY_DOUBLE:
                    # Choose 1 or 2 random category/tier combination to be daily double
                    previous_double = None
                    for _ in range(jeopardy_round):
                        category = ordered_categories[random.randint(0, 5)]
                        tier = random.randint(0, 4)

                        while (category, tier) == previous_double:
                            category = ordered_categories[random.randint(0, 5)]
                            tier = random.randint(0, 4)

                        previous_double = (category, tier)

                        used_questions[category][tier]["double"] = True

                if TRACK_UNUSED:
                    with open(USED_QUESTIONS_FILE, "w", encoding="utf-8") as fp:
                        json.dump(used_questions, fp, indent=4)

            for category in used_questions:
                for tier, info in enumerate(used_questions[category]):
                    questions_left = any(index not in info["used"] for index in range(len(questions[category]["tiers"][tier]["questions"])))
                    questions[category]["tiers"][tier]["active"] = (not TRACK_UNUSED or (info["active"] and questions_left))
                    questions[category]["tiers"][tier]["double"] = info["double"]

        selection_state = SelectionState(
            jeopardy_round,
            ROUND_NAMES[jeopardy_round-1],
            player_data,
            question_num + 1,
            player_turn,
            questions,
            ordered_categories
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = selection_state

        socket_io.emit("state_changed", to="contestants")

    return make_template_context("jeopardy/presenter_selection.html", **selection_state.__dict__)

@presenter_page.route("/finale")
def finale():
    if get_user_details() is None:
        return redirect_to_login("presenter.finale")

    question_id = 0

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    question = questions[FINALE_CATEGORY]["tiers"][-1]["questions"][question_id]
    category_name = questions[FINALE_CATEGORY]["name"]

    player_data = get_round_data(flask.request.args)[0]
    _sync_contestants(player_data, flask.current_app.config["JEOPARDY_DATA"]["contestants"])

    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    for data in player_data:
        disc_id = int(data["disc_id"])
        wager = contestants[disc_id].finale_wager
        data["wager"] = wager if wager > 0 else "intet"
        answer = contestants[disc_id].finale_answer
        data["answer"] = "ikke" if answer is None else f"'{answer}'"

    finale_state = FinaleState(
        FINALE_ROUND,
        ROUND_NAMES[FINALE_ROUND-1], 
        player_data,
        question,
        category_name
    )

    flask.current_app.config["JEOPARDY_DATA"]["state"] = finale_state

    return make_template_context("jeopardy/presenter_finale.html", **finale_state.__dict__)

@presenter_page.route("/endscreen")
def endscreen():
    if get_user_details() is None:
        return redirect_to_login("presenter.endscreen")

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        player_data = get_round_data(flask.request.args)[0]

        # Game over! Go to endscreen
        player_data = sorted(
            (
                dict(map(lambda x: (x, int(data[x]) if x == "disc_id" else data[x]), data))
                for data in player_data
            ),
            key=lambda x: x["score"],
            reverse=True
        )

        jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
        contestants = jeopardy_data["contestants"]

        avatar = contestants[player_data[0]["disc_id"]].avatar

        avatars = [avatar]
        ties = 0
        for index, data in enumerate(player_data[1:], start=1):
            if player_data[index-1]["score"] > data["score"]:
                break

            avatar = contestants[data["disc_id"]].avatar
            avatars.append(avatar)

            ties += 1

        if ties == 0:
            winner_desc = f'<span style="color: #{player_data[0]["color"]}; font-weight: 800;">{player_data[0]["name"]}</span> wonnered!!! All hail the king!'

        elif ties == 1:
            winner_desc = (
                f'<span style="color: #{player_data[0]["color"]}">{player_data[0]["name"]}</span> '
                f'og <span style="color: #{player_data[1]["color"]}; font-weight: 800;">{player_data[1]["name"]}</span> '
                "har lige mange point, de har begge to vundet!!!"
            )

        elif ties > 1:
            players_tied = ", ".join(
                f'<span style="color: #{data["color"]}; font-weight: 800;">{data["name"]}</span>' for data in player_data[:ties]
            ) + f', og <span style="color: #{player_data[ties]["color"]}; font-weight: 800;">{player_data[ties]["name"]}</span>'

            winner_desc = (
                f"{players_tied} har alle lige mange point! De har alle sammen vundet!!!"
            )

        logger.bind(event="jeopardy_player_data", player_data=player_data).info(f"Jeopardy player data at endscreen: {player_data}")

        winner_ids = [str(data["disc_id"]) for data in player_data[:ties + 1]]
        endscreen_state = EndscreenState(
            4, "Endscreen", player_data, winner_desc, winner_ids, avatars
        )

        jeopardy_data["state"] = endscreen_state

        socket_io.emit("state_changed", to="contestants")

    return make_template_context("jeopardy/presenter_endscreen.html", **endscreen_state.__dict__)

@presenter_page.route("/cheatsheet")
def cheatsheet():
    if get_user_details() is None:
        return redirect_to_login("presenter.cheatsheet")

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    return make_template_context("jeopardy/cheat_sheet.html", questions=questions)

@socket_io.event
def presenter_joined():
    join_room("presenter")

@socket_io.event
def join_lobby(disc_id: str, nickname: str, avatar: str, color: str):
    disc_id = int(disc_id)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

        turn_id = PLAYER_INDEXES.index(disc_id)
        contestant = active_contestants[disc_id]
        # Check if attributes for contestant has changed
        attributes = [("index", turn_id), ("name", nickname), ("color", color)]
        for attr_name, value in attributes:
            if getattr(contestant, attr_name) != value:
                setattr(contestant, attr_name, value)

        emit("player_joined", (str(disc_id), turn_id, nickname, avatar, color), to="presenter")

        # Add socket IO session ID to contestant and join 'contestants' room
        print(f"User with name {nickname}, disc_id {disc_id}, and SID {flask.request.sid} joined the lobby")
        leave_room("contestants", contestant.sid)
        join_room("contestants")
        contestant.sid = flask.request.sid
        active_contestants[disc_id] = contestant

@socket_io.event
def mark_question_active(game_id: str, user_id: str):
    

@socket_io.event
def enable_buzz(active_players_str: str):
    active_player_ids = json.loads(active_players_str)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state: QuestionState = jeopardy_data["state"]

    active_ids = []
    for contestant in contestants.values():
        contestant.latest_buzz = None
        if active_player_ids[contestant.index]:
            active_ids.append(contestant.index)

    state.buzz_winner_decided = False
    state.question_asked_time = time()

    emit("buzz_enabled", active_ids, to="contestants")

@socket_io.event
def enable_powerup(disc_id: str, power_id: str):
    if disc_id is not None:
        disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestants: Dict[str, Contestant] = jeopardy_data["contestants"]

    if disc_id is not None:
        player_ids = [disc_id]

    else:
        player_ids = list(contestants.keys())

    skip_contestants = []
    for player_id in player_ids:
        contestant = contestants[player_id]
        power_up = contestant.get_power(power_id)
        if power_up.used:
            skip_contestants.append(contestant.sid)
            continue

        power_up.enabled = True

    state.power_use_decided = False

    if skip_contestants != [] and disc_id is not None:
        return

    send_to = contestants[disc_id].sid if disc_id is not None else "contestants"
    emit("power_up_enabled", power_id, to=send_to, skip_sid=skip_contestants)

@socket_io.event
def disable_powerup(disc_id: str | None, power_id: str | None):
    if disc_id is not None:
        disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestants: Dict[str, Contestant] = jeopardy_data["contestants"]

    if disc_id is not None:
        player_ids = [disc_id]

    else:
        player_ids = list(contestants.keys())

    power_ids = [power_id] if power_id is not None else list(POWER_UP_IDS)
    for player_id in player_ids:
        contestant = contestants[player_id]
        for pow_id in power_ids:
            power = contestant.get_power(pow_id)
            power.enabled = False

    state.power_use_decided = True

    send_to = contestants[disc_id].sid if disc_id is not None else "contestants"
    emit("power_ups_disabled", power_ids, to=send_to)

@socket_io.event
def buzzer_pressed(disc_id: str):
    disc_id = int(disc_id)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state: QuestionState = jeopardy_data["state"]

    contestant = contestants.get(disc_id)

    if contestant is None:
        return

    contestant.latest_buzz = time() - (contestant.ping / 1000)
    time_taken = f"{contestant.latest_buzz - state.question_asked_time:.2f}"
    contestant.buzzes += 1

    emit("buzz_received", (contestant.index, time_taken), to="presenter")
    print(f"Buzz from {contestant.name} (#{contestant.index}, {contestant.sid}): {contestant.latest_buzz}, ping: {contestant.ping}", flush=True)

    sleep(min(max(max(c.ping / 1000, 0.01) for c in contestants.values()), 1))

    # Make sure no other requests can declare a winner by using a lock
    with flask.current_app.config["JEOPARDY_BUZZ_LOCK"]:
        if state.buzz_winner_decided:
            return

        state.buzz_winner_decided = True

        earliest_buzz_time = time()
        earliest_buzz_player = None
        for c in contestants.values():
            if c.latest_buzz is not None and c.latest_buzz < earliest_buzz_time:
                earliest_buzz_time = c.latest_buzz
                earliest_buzz_player = c

        # Reset buzz-in times
        for c in contestants.values():
            c.latest_buzz = None

        emit("buzz_winner", to=earliest_buzz_player.sid)
        emit("buzz_winner", earliest_buzz_player.index, to="presenter")
        emit("buzz_loser", to="contestants", skip_sid=earliest_buzz_player.sid)

@socket_io.event
def correct_answer(turn_id: int, value: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.hits += 1
    contestant.score += value

@socket_io.event
def wrong_answer(turn_id: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.misses += 1

@socket_io.event
def disable_buzz():
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    with flask.current_app.config["JEOPARDY_BUZZ_LOCK"]:
        state.buzz_winner_decided = True

    emit("buzz_disabled", to="contestants")

@socket_io.event
def first_turn(turn_id: int):
    emit("turn_chosen", int(turn_id), to="contestants")

@socket_io.event
def use_power_up(disc_id: str, power_id: str):
    disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestant: Contestant = jeopardy_data["contestants"].get(disc_id)

    if contestant is None:
        return

    print(f"Power up '{power_id}' used by {contestant.name}", flush=True)

    with flask.current_app.config["JEOPARDY_POWER_LOCK"]:
        if state.power_use_decided:
            return

        state.power_use_decided = True

        power_up = contestant.get_power(power_id)
        if power_up.used: # Contestant has already used this power_up
            return

        power_up.used = True

        if power_id in ("hijack", "rewind"):
            emit("buzz_disabled", to="contestants", skip_sid=contestant.sid)

        emit("power_ups_disabled", list(POWER_UP_IDS), to="contestants")
        emit("power_up_used", (contestant.index, power_id), to="presenter")
        emit("power_up_used", power_id, to=contestant.sid)

@socket_io.event
def enable_finale_wager():
    emit("finale_wager_enabled", to="contestants")

@socket_io.event
def reveal_finale_category():
    emit("finale_category_revealed", to="contestants")
