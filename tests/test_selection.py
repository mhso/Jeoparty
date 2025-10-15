import asyncio
import pytest

from jeoparty.api.config import get_avatar_path
from jeoparty.api.enums import PowerUpType
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY
from tests.config import PRESENTER_USER_ID

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

    async with ContextHandler(database) as context:
        game_page, game_id = await context.create_game(pack_name)

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

            
