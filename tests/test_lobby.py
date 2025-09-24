import pytest

from tests.browser_context import ContextHandler

@pytest.mark.asyncio
async def test_create_game_defaults(database):
    pack_name = "LoL Jeopardy v5"
    expected_title = "User 123's Game"
    expected_rounds = 2
    expected_contestants = 5
    expected_doubles = True
    expected_powerups = True

    async with ContextHandler(database) as context:
        lobby_page = await context.create_game(pack_name)

        title_elem = await lobby_page.query_selector("#menu-game-title")

        assert await title_elem.text_content() == expected_title
