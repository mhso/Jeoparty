import os

import pytest

from jeoparty.api.config import get_avatar_path
from tests.browser_context import ContextHandler, rgb_to_hex

@pytest.mark.asyncio
async def test_join_lobby_defaults(database, locales):
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
    contestant_avatar = "http://localhost:5006/static/img/avatars/questionmark.png"

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name))[1]

        placeholder_elem = await context.presenter_page.query_selector("#menu-no-contestants-placeholder")
        assert await placeholder_elem.is_visible()

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/lobby"]

            assert game_data.game_contestants == []

            contestants_placeholder = await context.presenter_page.query_selector("#menu-no-contestants-placeholder")
            assert await contestants_placeholder.text_content() == locale["none_joined"]

            for index, (name, color) in enumerate(zip(contestant_names, contestant_colors)):
                # Add a contestant to the game
                contestant_id = (await context.join_lobby(game_data.join_code, name, color))[1]
                session.refresh(game_data)

                assert len(game_data.game_contestants) == index + 1

                contestant = game_data.game_contestants[index]

                assert contestant.contestant_id == contestant_id

                await context.screenshot_views(index)

                assert not await placeholder_elem.is_visible()
                contestants_wrapper = await context.presenter_page.query_selector("#menu-contestants")

                presenter_contestant_entries = await contestants_wrapper.query_selector_all(".menu-contestant-entry")
                assert len(presenter_contestant_entries) == index + 1

                assert await presenter_contestant_entries[index].get_attribute("id") == f"player_{contestant.id}"

                avatar_elem = await presenter_contestant_entries[index].query_selector(".menu-contestant-avatar")
                assert await avatar_elem.get_attribute("src") == contestant_avatar

                presenter_entry_style = await presenter_contestant_entries[index].get_property("style")
                border_color = await presenter_entry_style.get_property("borderColor")
                assert rgb_to_hex(await border_color.json_value()) == color

                contestant_placeholder = await context.contestant_pages[contestant_id].query_selector("#contestant-game-waiting")
                assert await contestant_placeholder.is_visible()

                await context.assert_contestant_values(contestant_id, name, color, contestant_avatar, 0, 0, 0, 0)

@pytest.mark.asyncio
async def test_rejoin_lobby(database):
    pack_name = "Test Pack"
    contestant_name_1 = "Guy"
    contestant_name_2 = "Gal"
    contestant_color_1 = "#1155EE"
    contestant_color_2 = "#009E18"
    contestant_avatar_1 = "/static/img/avatars/questionmark.png"
    contestant_avatar_2 = "/mnt/d/mhooge/jeoparty/src/jeoparty/app/static/img/avatars/f909a1fc-d673-469d-ad82-b51ed7672e7f.png"

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)

            contestant_id_1 = (await context.join_lobby(game_data.join_code, contestant_name_1, contestant_color_1))[1]

            session.refresh(game_data)
            contestant = game_data.game_contestants[0]

            await context.assert_contestant_values(
                contestant_id_1,
                contestant_name_1,
                contestant_color_1,
                contestant_avatar_1,
                0,
                0,
                0,
                0,
            )

            await context.assert_presenter_values(
                contestant.id,
                contestant_name_1,
                contestant_color_1,
                contestant_avatar_1,
            )

            # Go back and change contestant name and color and join again
            page = context.contestant_pages[contestant_id_1]
            await page.go_back()

            contestant_id_2 = (await context.join_lobby(game_data.join_code, contestant_name_2, contestant_color_2, contestant_avatar_2, page))[1]

            assert contestant_id_1 == contestant_id_2

            session.refresh(game_data)
            contestant = game_data.game_contestants[0]

            expected_avatar = f"{get_avatar_path().split("/app")[1]}/{contestant_id_1}.png"
            await context.assert_contestant_values(
                contestant_id_1,
                contestant_name_2,
                contestant_color_2,
                expected_avatar,
                0,
                0,
                0,
                0,
            )

            await context.assert_presenter_values(
                contestant.id,
                contestant_name_2,
                contestant_color_2,
                expected_avatar,
            )

            assert os.path.exists(f"{get_avatar_path()}/{contestant_id_1}.png")

@pytest.mark.asyncio
async def test_errors(database):
    pack_name = "Test Pack"

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)

            # Try to join with too short of a name
            too_short_name = "X"
            page, contestant_id = await context.join_lobby(game_data.join_code, too_short_name)

            # Assert that player failed to join
            assert contestant_id is None
            session.refresh(game_data)
            assert game_data.game_contestants == []

            error_elem = await page.query_selector("#contestant-lobby-error")
            assert await error_elem.text_content() == "Error when joining lobby: 'Name' should have at least 2 characters"

            # Try to join with too long of a name
            too_long_name = "Contestant With Way Too Long Name"
            page, contestant_id = await context.join_lobby(game_data.join_code, too_long_name)

            # Assert that player failed to join
            assert contestant_id is None
            session.refresh(game_data)
            assert game_data.game_contestants == []

            error_elem = await page.query_selector("#contestant-lobby-error")
            assert await error_elem.text_content() == "Error when joining lobby: 'Name' should have at most 16 characters"

            # Try to join with a name that has invalid characters
            invalid_name = "Inv@l!d Nam£"
            page, contestant_id = await context.join_lobby(game_data.join_code, invalid_name)

            # Assert that player failed to join
            assert contestant_id is None
            session.refresh(game_data)
            assert game_data.game_contestants == []

            error_elem = await page.query_selector("#contestant-lobby-error")
            assert await error_elem.text_content() == "Error when joining lobby: 'Name' contains invalid characters"

            # # Try to join with an invalid color
            # name = "Regular Name"
            # invalid_color = "redd"

            # async def dialog_callback(dialog: Dialog):
            #     assert dialog.message == f"Invalid color: '{invalid_color}', please provide a valid color."
            #     await dialog.accept()

            # page.on("dialog", dialog_callback)

            # contestant_id = (await context.join_lobby(game_data.join_code, name, invalid_color, page=page))[1]

            # # Assert that player failed to join
            # assert contestant_id is None
            # session.refresh(game_data)
            # assert game_data.game_contestants == []
