import asyncio
import pytest

from playwright.async_api import Dialog

from jeoparty.api.enums import PowerUpType, StageType
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY

@pytest.mark.asyncio
async def test_first_turn(database):
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
    expected_category_headers = [
        "Category Uno",
        "Category Dos",
    ]
    expected_question_values = [
        ["100"],
        ["100", "200"]
    ]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            session.refresh(game_data)
            assert len(game_data.game_contestants) == len(contestant_names)

            await context.start_game()

            session.refresh(game_data)
            
            assert game_data.get_contestant_with_turn() is None
            assert game_data.round == 1
            assert game_data.stage == StageType.SELECTION
            
            num_dailies = sum(bool(q.daily_double) for q in game_data.get_questions_for_round())
            assert num_dailies == 1

            # Assert initial conditions
            for contestant_id, name, color in zip(context.contestant_pages, contestant_names, contestant_colors):
                game_contestant = game_data.get_contestant(contestant_id=contestant_id)
                await context.assert_contestant_values(contestant_id, name, color, score=0, buzzes=0, hits=0, misses=0)
                await context.assert_presenter_values(
                    game_contestant.id,
                    name,
                    color,
                    score=0,
                    hits=0,
                    misses=0,
                    used_power_ups={power.value: False for power in PowerUpType}
                )

            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            async def first_turn_chosen():
                return await context.presenter_page.evaluate("playerTurn != null")

            await context.wait_for_event(first_turn_chosen)

            await asyncio.sleep(1)

            session.refresh(game_data)

            contestant_with_turn = game_data.get_contestant_with_turn()
            assert contestant_with_turn is not None

            active_elem = await context.presenter_page.query_selector(".active-contestant-entry")
            assert await active_elem.evaluate(f"(e) => e.classList.contains('footer-contestant-{contestant_with_turn.id}')")

            # Assert that categories and question values are correct
            category_entries = await context.presenter_page.query_selector_all(".selection-category-entry")
            for entry, expected_header, expected_values in zip(category_entries, expected_category_headers, expected_question_values):
                header = await entry.query_selector(".selection-category-header")

                assert (await header.text_content()).strip() == expected_header

                question_entries = await entry.query_selector_all(".selection-question-box")
                for entry, expected_value in zip(question_entries, expected_values):
                    assert (await entry.text_content()).strip() == expected_value

@pytest.mark.asyncio
async def test_new_round(database):
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
        game_id = (await context.create_game(pack_name))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            session.refresh(game_data)
            assert len(game_data.game_contestants) == len(contestant_names)
            assert game_data.round == 1

            # Mark all but one question in the round as used
            questions_for_round = game_data.get_questions_for_round()
            for question in questions_for_round:
                question.active = False
                question.used = True

            questions_for_round[0].active = True
            questions_for_round[0].used = False

            database.save_models(*questions_for_round)

            # Go to selection page
            await context.open_selection_page(game_id)

            session.refresh(game_data)
            questions = game_data.get_questions_for_round()

            assert game_data.round == 2
            assert game_data.stage == StageType.SELECTION
            assert all(q.question.category.round.round == 2 for q in questions)
            assert not any(q.used for q in questions)

            num_dailies = sum(bool(q.daily_double) for q in questions)
            assert num_dailies == 2

@pytest.mark.asyncio
async def test_finale_wager_valid(database, locales):
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

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/selection"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            game_data.round = 2
            database.save_models(game_data)

            session.refresh(game_data)
            assert len(game_data.game_contestants) == len(contestant_names)

            for contestant, score in zip(game_data.game_contestants, contestant_scores):
                contestant.score = score

            # Mark all but one question in the round as used
            questions_for_round = game_data.get_questions_for_round()
            for question in questions_for_round:
                question.active = False
                question.used = True

            questions_for_round[0].active = True
            questions_for_round[0].used = False

            database.save_models(*questions_for_round)

            # Go to selection page
            await context.open_selection_page(game_id)

            session.refresh(game_data)
            questions = game_data.get_questions_for_round()

            assert game_data.round == 3
            assert game_data.stage == StageType.FINALE_WAGER
            assert all(q.question.category.round.round == 3 for q in questions)
            assert not any(q.used for q in questions)
            assert len(questions) == 1

            round_name = questions[0].question.category.round.name
            category_name = questions[0].question.category.name

            await context.assert_finale_wager_values(
                locale,
                round_name,
            )

            # Show finale category
            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            await context.assert_finale_wager_values(
                locale,
                round_name,
                category_name,
                False,
            )

            await asyncio.sleep(4)

            await context.assert_finale_wager_values(
                locale,
                round_name,
                category_name,
                True,
            )

            for contestant in game_data.game_contestants:
                await context.assert_contestant_values(
                    contestant.contestant_id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=contestant.score,
                    buzzes=contestant.buzzes,
                    hits=contestant.hits,
                    misses=contestant.misses,
                )
    
                await context.assert_presenter_values(
                    contestant.id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=contestant.score,
                    hits=contestant.hits,
                    misses=contestant.misses,
                    has_turn=False,
                    ready=False,
                )

            # Make valid wagers for each contestant
            wagers = [1000, 300, 400, 0]

            pending = (
                await asyncio.wait(
                    [
                        asyncio.create_task(context.make_wager(contestant.contestant_id, wager))
                        for contestant, wager in zip(game_data.game_contestants, wagers)
                    ],
                    timeout=10
                )
            )[1]

            assert len(pending) == 0

            for contestant in game_data.game_contestants:
                await context.assert_presenter_values(
                    contestant.id,
                    contestant.contestant.name,
                    contestant.contestant.color,
                    score=contestant.score,
                    hits=contestant.hits,
                    misses=contestant.misses,
                    has_turn=False,
                    ready=True,
                )

            session.refresh(game_data)

            # Assert that wagers are correctly saved
            for contestant, wager in zip(game_data.game_contestants, wagers):
                assert contestant.finale_wager == wager

            # Go to finale question page
            async with await context.wait_until_ready():
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            session.refresh(game_data)

            active_question = game_data.get_active_question()

            assert game_data.round == 3
            assert game_data.stage == StageType.FINALE_QUESTION
            assert context.presenter_page.url.endswith("/question")

            await context.assert_question_values(
                active_question,
                False,
                False,
                is_finale=True,
            )

# async def test_finale_wager_invalid(database, locales):
#     pack_name = "Test Pack"
#     contestant_names = [
#         "Contesto Uno",
#         "Contesto Dos",
#         "Contesto Tres",
#         "Contesto Quatro",
#     ]
#     contestant_colors = [
#         "#1FC466",
#         "#1155EE",
#         "#BD1D1D",
#         "#CA12AF",
#     ]
#     contestant_scores = [
#         -500, 300, 1200, 0
#     ]

#     async with ContextHandler(database) as context:
#         game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

#         with database as session:
#             game_data = database.get_game_from_id(game_id)
#             locale = locales[game_data.pack.language.value]["pages"]["contestant/game"]

#             # Add contestants to the game
#             for name, color in zip(contestant_names, contestant_colors):
#                 await context.join_lobby(game_data.join_code, name, color)

#             # Make an invalid wager
#             async def on_dialog(dialog: Dialog):
#                 assert dialog.message == f"{locale["invalid_wager"]} 1000"
#                 await dialog.dismiss()

#             await context.make_wager(game_data.game_contestants[0].contestant_id, 1100, on_dialog)
