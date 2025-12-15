import asyncio
from math import ceil

import pytest

from jeoparty.api.enums import StageType
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY
from tests import create_contestant_data, create_game

@pytest.mark.asyncio
async def test_freeze(database, locales):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, daily_doubles=False)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[1], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("question_image"), game_data.get_questions_for_round()))

            active_player.has_turn = True
            active_question.active = True

            database.save_models(active_player, active_question)

            # Open question page and show question
            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            await context.show_question()

            # Buzz in and use freeze
            await context.hit_buzzer(active_player.contestant_id)

            await asyncio.sleep(1)

            await context.assert_contestant_values(
                active_player.contestant_id,
                buzzer_status="inactive",
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": True, "freeze": True, "rewind": False},
            )

            await context.use_power_up(active_player.contestant_id, "freeze")

            frozenCountdownElem = await context.presenter_page.query_selector(".question-countdown-frozen")
            assert float(await frozenCountdownElem.evaluate("(e) => window.getComputedStyle(e).opacity")) > 0

            await context.assert_question_values(
                active_question,
                game_feed=[
                    f"{contestant_names[1]} {locale['game_feed_buzz_1']} " + r"\d{1,3}\.\d{2} " + locale['game_feed_buzz_2'],
                    f"{contestant_names[1]} {locale['game_feed_power_1']} freeze {locale['game_feed_power_2']}!",
                ]
            )

            # Assert countdown is paused
            assert await context.presenter_page.evaluate("countdownPaused")

            countdown_elem = await context.presenter_page.query_selector(".question-countdown-text")
            seconds_before = await countdown_elem.text_content()

            await asyncio.sleep(1.5)

            seconds_now = await countdown_elem.text_content()

            assert seconds_before == seconds_now

            for contestant in game_data.game_contestants:
                await context.assert_presenter_values(
                    contestant.id,
                    used_power_ups={"hijack": False, "freeze": contestant.id == active_player.id, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": contestant.id == active_player.id, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

            # Answer the question
            await context.answer_question(active_player.contestant_id, key=1)

            await context.assert_presenter_values(
                active_player.id,
                score=200,
                hits=1,
                misses=0,
            )

            # Assert that we go back to selection page after everyone answered wrong
            async with context.presenter_page.expect_navigation():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert context.presenter_page.url.endswith("/selection")
            assert game_data.stage == StageType.SELECTION

@pytest.mark.asyncio
async def test_rewind_before_buzz(database, locales):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, daily_doubles=False)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[1], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("question_image"), game_data.get_questions_for_round()))

            active_player.has_turn = True
            active_question.active = True

            database.save_models(active_player, active_question)

            # Open question page and show question
            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            await context.show_question()

            # Buzz in and answer wrong
            await context.hit_buzzer(active_player.contestant_id)
            await asyncio.sleep(1)

            await context.answer_question(active_player.contestant_id, key=2)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=-active_question.question.value if is_active else 0,
                    hits=0,
                    misses=int(is_active),
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=-active_question.question.value if is_active else 0,
                    buzzes=int(is_active),
                    hits=0,
                    misses=int(is_active),
                    buzzer_status="inactive" if is_active else "active",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                )

            # Use rewind power-up to cancel the wrong answer
            await context.use_power_up(active_player.contestant_id, "rewind")

            await context.assert_question_values(
                active_question,
                game_feed=[
                    f"{contestant_names[1]} {locale['game_feed_power_1']} rewind {locale['game_feed_power_2']}!",
                ]
            )

            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_active,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=int(is_active),
                    hits=0,
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                    enabled_power_ups={"hijack": False, "freeze": is_active, "rewind": False},
                )

            # Answer correctly this time
            await context.answer_question(active_player.contestant_id, key=1)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=active_question.question.value if is_active else 0,
                    hits=int(is_active),
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=active_question.question.value if is_active else 0,
                    buzzes=int(is_active),
                    hits=int(is_active),
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

@pytest.mark.asyncio
async def test_rewind_after_buzz(database, locales):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, daily_doubles=False)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            player_1 = next(filter(lambda c: c.contestant.name == contestant_names[1], game_data.game_contestants))
            player_2 = next(filter(lambda c: c.contestant.name == contestant_names[3], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("question_image"), game_data.get_questions_for_round()))

            player_1.has_turn = True
            active_question.active = True

            database.save_models(player_1, active_question)

            # Open question page and show question
            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            await context.show_question()

            # Buzz in and answer wrong
            await context.hit_buzzer(player_1.contestant_id)
            await asyncio.sleep(1)

            await context.answer_question(player_1.contestant_id, key=2)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == player_1.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=-active_question.question.value if is_active else 0,
                    hits=0,
                    misses=int(is_active),
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=-active_question.question.value if is_active else 0,
                    buzzes=int(is_active),
                    hits=0,
                    misses=int(is_active),
                    buzzer_status="inactive" if is_active else "active",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": is_active},
                )

            # Have another player buzz in
            await context.hit_buzzer(player_2.contestant_id)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_p1 = contestant.id == player_1.id
                is_p2 = contestant.id == player_2.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=-active_question.question.value if is_p1 else 0,
                    hits=0,
                    misses=int(is_p1),
                    has_turn=is_p2,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=-active_question.question.value if is_p1 else 0,
                    buzzes=int(is_p1 or is_p2),
                    hits=0,
                    misses=int(is_p1),
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": is_p2, "rewind": is_p1},
                )

            # Use rewind power-up to cancel the wrong answer
            await context.use_power_up(player_1.contestant_id, "rewind")

            await context.assert_question_values(
                active_question,
                game_feed=[
                    f"{contestant_names[3]} {locale['game_feed_buzz_1']} " + r"\d{1,3}\.\d{2} " + locale['game_feed_buzz_2'],
                    f"{contestant_names[1]} {locale['game_feed_power_1']} rewind {locale['game_feed_power_2']}!",
                ]
            )

            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_p1 = contestant.id == player_1.id
                is_p2 = contestant.id == player_2.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_p1,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_p1},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=int(is_p1 or is_p2),
                    hits=0,
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_p1},
                    enabled_power_ups={"hijack": False, "freeze": is_p1, "rewind": False},
                )

            # Answer correctly this time
            await context.answer_question(player_1.contestant_id, key=1)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_p1 = contestant.id == player_1.id
                is_p2 = contestant.id == player_2.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=active_question.question.value if is_p1 else 0,
                    hits=int(is_p1),
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_p1},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=active_question.question.value if is_p1 else 0,
                    buzzes=int(is_p1 or is_p2),
                    hits=int(is_p1),
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": False, "freeze": False, "rewind": is_p1},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

@pytest.mark.asyncio
async def test_hijack_before_question(database, locales):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, daily_doubles=False)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[2], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("question_image"), game_data.get_questions_for_round()))
            active_question.active = True

            database.save_models(active_question)

            # Open question page and show question
            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            # Use rewind power-up to cancel the wrong answer
            await context.use_power_up(active_player.contestant_id, "hijack")

            await context.assert_question_values(
                active_question,
                game_feed=[
                    f"{active_player.contestant.name} {locale['game_feed_power_1']} hijack {locale['game_feed_power_2']}!",
                ]
            )

            await context.show_question()

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_active,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=0,
                    hits=0,
                    misses=0,
                    buzzer_status="active" if is_active else "inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

            # Buzz in and answer correctly
            await context.hit_buzzer(active_player.contestant_id)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_active,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=int(is_active),
                    hits=0,
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": is_active, "rewind": False},
                )

            await context.answer_question(active_player.contestant_id, key=1)
            await asyncio.sleep(1)

            active_score = ceil(active_question.question.value * 1.5)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=active_score if is_active else 0,
                    hits=int(is_active),
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=active_score if is_active else 0,
                    buzzes=int(is_active),
                    hits=int(is_active),
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

@pytest.mark.asyncio
async def test_hijack_after_question(database, locales):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, daily_doubles=False)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[2], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("question_image"), game_data.get_questions_for_round()))
            active_question.active = True

            database.save_models(active_question)

            # Open question page and show question
            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            await context.show_question()

            # Use rewind power-up to cancel the wrong answer
            await context.use_power_up(active_player.contestant_id, "hijack")

            await context.assert_question_values(
                active_question,
                game_feed=[
                    f"{active_player.contestant.name} {locale['game_feed_power_1']} hijack {locale['game_feed_power_2']}!",
                ]
            )

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_active,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=0,
                    hits=0,
                    misses=0,
                    buzzer_status="active" if is_active else "inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )

            # Buzz in and answer correctly
            await context.hit_buzzer(active_player.contestant_id)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=is_active,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=0,
                    buzzes=int(is_active),
                    hits=0,
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": is_active, "rewind": False},
                )

            await context.answer_question(active_player.contestant_id, key=1)
            await asyncio.sleep(1)

            for contestant in game_data.game_contestants:
                is_active = contestant.id == active_player.id

                await context.assert_presenter_values(
                    contestant.id,
                    score=active_question.question.value if is_active else 0,
                    hits=int(is_active),
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                )

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    score=active_question.question.value if is_active else 0,
                    buzzes=int(is_active),
                    hits=int(is_active),
                    misses=0,
                    buzzer_status="inactive",
                    used_power_ups={"hijack": is_active, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
                )
