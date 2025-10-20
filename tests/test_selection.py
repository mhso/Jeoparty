import asyncio
import pytest

from jeoparty.api.enums import PowerUpType
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
