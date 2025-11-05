import asyncio
import pytest

from jeoparty.api.enums import StageType
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY

@pytest.mark.asyncio
async def test_first_round(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[0], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("choices"), game_data.game_questions))

            active_player.has_turn = True
            active_question.active = True

            database.save_models(active_player, active_question)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            # Assert that initial values contestant/presenter values are correct
            assert game_data.stage == StageType.QUESTION
            assert game_data.round == 1

            for contestant, name, color in zip(game_data.game_contestants, contestant_names, contestant_colors):
                assert contestant.power_ups != []

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    name,
                    color,
                    score=0,
                    buzzes=0,
                    hits=0,
                    misses=0,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": True, "freeze": False, "rewind": False},
                )

                await context.assert_presenter_values(
                    contestant.id,
                    name,
                    color,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False}
                )

            # Assert that the question view elements are correct
            await context.assert_question_values(
                active_question,
                question_visible=False,
                answer_visible=False,
            )

            await context.show_question()

            await asyncio.sleep(0.5)

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
            )

            # Let a player buzz in
            wrong_buzz_player = next(filter(lambda c: c.contestant.name == contestant_names[2], game_data.game_contestants))
            await context.hit_buzzer(wrong_buzz_player.contestant_id)

            await context.assert_contestant_values(
                wrong_buzz_player.contestant_id,
                contestant_names[2],
                contestant_colors[2],
                score=0,
                buzzes=0, # Buzzes only update on page refresh, so here it's still 0
                hits=0,
                misses=0,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": True, "freeze": True, "rewind": False},
            )

            await context.assert_presenter_values(
                wrong_buzz_player.id,
                wrong_buzz_player.contestant.name,
                wrong_buzz_player.contestant.color,
                score=0,
                hits=0,
                misses=0,
                has_turn=True,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
                game_feed=[f"{contestant_names[2]} {locale['game_feed_buzz_1']} " + r"\d{1,3}\.\d{2} " + locale['game_feed_buzz_2']]
            )

            # Have the player answer the question wrong
            await context.answer_question(choice="Eggs")

            await context.assert_contestant_values(
                wrong_buzz_player.contestant_id,
                contestant_names[2],
                contestant_colors[2],
                score=0,
                buzzes=0,
                hits=0,
                misses=0, # Misses only update on page refresh, so here it's still 0
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": False, "freeze": False, "rewind": True},
            )

            await context.assert_presenter_values(
                wrong_buzz_player.id,
                wrong_buzz_player.contestant.name,
                wrong_buzz_player.contestant.color,
                score=-active_question.question.value,
                hits=0,
                misses=0, # Misses only update on page refresh, so here it's still 0
                has_turn=False,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
                correct_answer=False,
                wrong_answer_text=locale["wrong_answer_given"],
            )

            # Have another player buzz in
            correct_buzz_player = next(filter(lambda c: c.contestant.name == contestant_names[1], game_data.game_contestants))
            await context.hit_buzzer(correct_buzz_player.contestant_id)

            await context.assert_contestant_values(
                correct_buzz_player.contestant_id,
                correct_buzz_player.contestant.name,
                correct_buzz_player.contestant.color,
                score=0,
                buzzes=0, # Buzzes only update on page refresh, so here it's still 0
                hits=0,
                misses=0,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": False, "freeze": True, "rewind": False},
            )

            # Assert values for the player who buzzed earlier
            await context.assert_contestant_values(
                wrong_buzz_player.contestant_id,
                wrong_buzz_player.contestant.name,
                wrong_buzz_player.contestant.color,
                score=0,
                buzzes=0, # Buzzes only update on page refresh, so here it's still 0
                hits=0,
                misses=0,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": False, "freeze": False, "rewind": True},
            )

            await context.assert_presenter_values(
                correct_buzz_player.id,
                correct_buzz_player.contestant.name,
                correct_buzz_player.contestant.color,
                score=0,
                hits=0,
                misses=0,
                has_turn=True,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
                game_feed=[f"{contestant_names[1]} {locale['game_feed_buzz_1']} " + r"\d{1,3}\.\d{2} " + locale['game_feed_buzz_2']]
            )

            # Have the player answer the question correctly
            await context.answer_question(choice="42")

            await context.assert_contestant_values(
                correct_buzz_player.contestant_id,
                contestant_names[1],
                contestant_colors[1],
                score=0,
                buzzes=0,
                hits=0,
                misses=0,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": False, "freeze": False, "rewind": False},
            )

            await context.assert_presenter_values(
                correct_buzz_player.id,
                correct_buzz_player.contestant.name,
                correct_buzz_player.contestant.color,
                score=active_question.question.value // 2,
                hits=0,
                misses=0,
                has_turn=False,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
                correct_answer=True,
            )

            # Finish the question and go to selection screen
            async with await context.wait_until_ready():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert game_data.stage == StageType.SELECTION
            assert context.presenter_page.url.endswith("/selection")

            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("choices"), game_data.game_questions))

            assert not active_question.active
            assert active_question.used

            # Assert final set of values for all contestants
            for contestant in game_data.game_contestants:
                buzzes = 0
                misses = 0
                hits = 0
                score = 0
                has_turn = False

                if contestant == wrong_buzz_player:
                    buzzes = 1
                    misses = 1
                    score = -active_question.question.value
                elif contestant == correct_buzz_player:
                    buzzes = 1
                    hits = 1
                    score = active_question.question.value // 2
                    has_turn = True

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=score,
                    buzzes=buzzes,
                    hits=hits,
                    misses=misses,
                )

                await context.assert_presenter_values(
                    contestant.id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=score,
                    hits=hits,
                    misses=misses,
                    has_turn=has_turn,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False}
                )

@pytest.mark.asyncio
async def test_all_wrong_buzzes(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()

            session.refresh(game_data)

            # Set question 2 as the active question
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("tips"), game_data.game_questions))

            active_question.active = True

            database.save_models(active_question)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            await context.show_question()

            for contestant in game_data.game_contestants:
                await context.assert_presenter_values(
                    contestant.id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=0,
                    hits=0,
                    misses=0,
                )
            
                await context.assert_contestant_values(
                    contestant.contestant_id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    buzzer_status="active"
                )

                await context.hit_buzzer(contestant.contestant_id)
                await asyncio.sleep(0.5)

                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
                await asyncio.sleep(0.5)

                await context.presenter_page.press("body", "2")
                await asyncio.sleep(0.5)

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    buzzer_status="inactive"
                )

                await context.assert_presenter_values(
                    contestant.id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=-active_question.question.value,
                    hits=0,
                    misses=1,
                )

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=True,
                correct_answer=False,
                wrong_answer_text=locale["wrong_answer_given"],
            )

            # Assert that we go back to selection page after everyone answered wrong
            async with context.presenter_page.expect_navigation():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert context.presenter_page.url.endswith("/selection")
            assert game_data.stage == StageType.SELECTION

@pytest.mark.asyncio
async def test_time_runs_out(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()

            session.refresh(game_data)

            # Set question 2 as the active question
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("tips"), game_data.game_questions))
            active_question.active = True

            database.save_models(active_question)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            wrong_answer_elem = await context.presenter_page.query_selector("#question-answer-wrong")

            async def wrong_answer_visible():
                return await wrong_answer_elem.is_visible()

            await context.show_question()

            await context.wait_for_event(wrong_answer_visible, timeout=active_question.question.category.buzz_time + 2)

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=True,
                correct_answer=False,
                wrong_answer_text=locale["wrong_answer_time"],
            )

            # Assert that we go back to selection page after everyone answered wrong
            async with context.presenter_page.expect_navigation():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert context.presenter_page.url.endswith("/selection")
            assert game_data.stage == StageType.SELECTION

@pytest.mark.asyncio
async def test_question_aborted(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()

            session.refresh(game_data)

            # Set question 2 as the active question
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("tips"), game_data.game_questions))
            active_question.active = True
            active_question.question.category.buzz_time = 0

            database.save_models(active_question)
            database.save_models(active_question.question.category)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            wrong_answer_elem = await context.presenter_page.query_selector("#question-answer-wrong")

            await context.show_question()

            await asyncio.sleep(2)

            await context.screenshot_views()

            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
            await asyncio.sleep(1)

            await context.screenshot_views()

            assert await wrong_answer_elem.is_visible()

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=True,
                correct_answer=False,
                wrong_answer_text=locale["wrong_answer_cowards"],
            )

            # Assert that we go back to selection page after everyone answered wrong
            async with context.presenter_page.expect_navigation():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert context.presenter_page.url.endswith("/selection")
            assert game_data.stage == StageType.SELECTION

@pytest.mark.asyncio
async def test_daily_double_valid(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=True))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()
            session.refresh(game_data)

            active_player = game_data.game_contestants[-1]

            active_player.has_turn = True
            active_player.score = 700
            database.save_models(active_player)

            session.refresh(game_data)

            # Set daily double question as active
            active_question = next(filter(lambda q: q.daily_double, game_data.game_questions))
            active_question.active = True

            database.save_models(active_question)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            daily_header = await context.presenter_page.query_selector("#question-wager-wrapper > h3")
            assert await daily_header.text_content() == f"{locale['daily_double_wager_1']} {active_player.contestant.name} {locale['daily_double_wager_2']} (max 700)"

            # Make a valid wager
            await context.make_wager(active_player.contestant_id, 600)

            await context.show_question(True)

            # Have the contestant answer correctly
            if active_question.question.extra and "choices" in active_question.question.extra:
               await context.answer_question(choice="42")
            else:
               await context.answer_question(key=1)

            await context.assert_presenter_values(
                active_player.id,
                active_player.contestant.name,
                active_player.contestant.color,
                score=active_player.score + 600,
                hits=1,
                misses=0,
            )

            async with context.presenter_page.expect_navigation():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(active_player)

            assert active_player.has_turn
            assert active_player.score == 1300
            assert active_player.buzzes == 0
            assert active_player.hits == 1
            assert active_player.misses == 0

# @pytest.mark.asyncio
# async def test_daily_double_invalid(database, locales):
#     pass

# @pytest.mark.asyncio
# async def test_freeze_power(database, locales):
#     pass

# @pytest.mark.asyncio
# async def test_rewind_power(database, locales):
#     pass

# @pytest.mark.asyncio
# async def test_hijack_power(database, locales):
#     pass

@pytest.mark.asyncio
async def test_finale_question(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]
    contestant_scores = [
        -500, 300, 1200, 0
    ]
    contestant_wagers = [1000, 300, 700, 0]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            language_locale = locales[game_data.pack.language.value]
            locale = language_locale["pages"]["contestant/game"]
            locale.update(language_locale["pages"]["global"])

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            game_data.round = 3
            game_data.stage = StageType.FINALE_WAGER
            finale_question = game_data.get_questions_for_round()[0]
            finale_question.active = True

            database.save_models(finale_question, game_data)
            session.refresh(game_data)

            assert len(game_data.game_contestants) == len(contestant_names)

            for contestant, score, wager in zip(game_data.game_contestants, contestant_scores, contestant_wagers):
                contestant.score = score
                contestant.finale_wager = wager

            database.save_models(*game_data.game_contestants)

            await context.open_question_page(game_data.id)

            session.refresh(game_data)
            
            assert game_data.stage == StageType.FINALE_QUESTION

            await context.assert_question_values(
                game_data.get_active_question(),
                False,
                is_finale=True,
            )
    
            await context.show_question()

            # Have contestants write their answers
            answers = ["4", "4", "3"]

            pending = (
                await asyncio.wait(
                    [
                        asyncio.create_task(context.give_finale_answer(contestant.contestant_id, answer))
                        for contestant, answer in zip(game_data.game_contestants[:-1], answers)
                    ],
                    timeout=10
                )
            )[1]

            assert len(pending) == 0

            # Assert contestant values are correct
            for contestant, wager in zip(game_data.game_contestants, contestant_wagers):
                await context.assert_finale_question_values(
                    contestant.contestant_id,
                    locale,
                    finale_question.question.category.name,
                    finale_question.question.question,
                    wager,
                )

            await asyncio.sleep(2)

            # Finish the question and go to finale screen
            async with context.presenter_page.expect_navigation(timeout=10000):
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            assert game_data.stage == StageType.FINALE_RESULT
            assert context.presenter_page.url.endswith("/finale")
            for contestant, answer in zip(game_data.game_contestants, answers + [None]):
                assert contestant.finale_answer == answer

# @pytest.mark.asyncio
# async def test_undo(database, locales):
#     pass
