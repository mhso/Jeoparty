import pytest

from tests.browser_context import ContextHandler
from tests.config import PRESENTER_USER_ID

@pytest.mark.asyncio
async def test_join_lobby_defaults(database):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]

    async with ContextHandler(database) as context:
        await context.create_game(pack_name)

        placeholder_elem = await context.presenter_page.query_selector("#menu-no-contestants-placeholder")
        assert await placeholder_elem.is_visible()

        with database as session:
            game_data = database.get_games_for_user(PRESENTER_USER_ID)[0]

            assert game_data.game_contestants == []

            for index, name in enumerate(contestant_names):
                # Add a contestant to the game
                contestant_id = await context.join_lobby(game_data.join_code, name)
                await context.screenshot_views(index)

                session.refresh(game_data)

                assert len(game_data.game_contestants) == index + 1

                contestant = game_data.game_contestants[index]

                assert contestant.contestant_id == contestant_id

                assert not await placeholder_elem.is_visible()
                contestants_wrapper = await context.presenter_page.query_selector("#menu-contestants")

                contestant_entries = await contestants_wrapper.query_selector_all(".menu-contestant-entry")
                assert len(contestant_entries) == index + 1

                assert await contestant_entries[index].get_attribute("id") == f"player_{contestant.id}"

                avatar_elem = await contestant_entries[index].query_selector(".menu-contestant-avatar")
                assert await avatar_elem.get_attribute("src") == "http://localhost:5006/static/img/avatars/questionmark.png"


@pytest.mark.asyncio
async def test_rejoin_lobby(database):
    pack_name = "Test Pack"
    contestant_name = "Contestanto Uno"
    contestant_color = "#1155EE"

    async with ContextHandler(database) as context:
        await context.create_game(pack_name)
