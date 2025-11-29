from glob import glob
import os
import pytest
from sqlalchemy import text

from jeoparty.api.config import Config
from jeoparty.api.orm.models import Contestant, GameContestant
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY
from tests import create_contestant_data

async def _extract_bg_image(element):
    assert element is not None

    element_style = await element.get_property("style")
    url = await (await element_style.get_property("background-image")).json_value()
    img_src = url.removeprefix('url("').removesuffix('")')
    relative_path = img_src.split("static/")[1]

    assert os.path.exists(f"{Config.STATIC_FOLDER}/{relative_path}")

    return relative_path

@pytest.mark.asyncio
async def test_lobby(database):
    pack_name = "Test Pack"
    contestant_names, contestant_colors = create_contestant_data()

    async with ContextHandler(database) as context:
        with database as session:
            for theme in ("LAN", "Jul"):
                # Set active theme on the question pack
                theme_id = session.execute(text(f"SELECT id FROM themes WHERE name = '{theme}'")).scalar_one()
                session.execute(text(f"UPDATE question_packs SET theme_id = '{theme_id}' WHERE name = '{pack_name}'"))
                session.commit()

                game_id = (await context.create_game(pack_name, daily_doubles=False))[1]
                game_data = database.get_game_from_id(game_id)

                # Add contestants to the game
                for name, color in zip(contestant_names, contestant_colors):
                    await context.join_lobby(game_data.join_code, name, color)

                session.refresh(game_data)
                assert len(game_data.game_contestants) == len(contestant_names)

                # Assert presenter background image path is correct and that file exists
                bg_image_path = await _extract_bg_image(await context.presenter_page.query_selector(".bg-image"))

                assert bg_image_path == f"data/themes/{theme_id}/presenter_background.jpg"

                possible_avatars = set(
                    img.split("static/")[1]
                    for img in glob(f"{Config.STATIC_FOLDER}/data/themes/{theme_id}/contestant_backgrounds/*")
                )
                len_before = len(possible_avatars)

                # Assert same for contestant backgrounds
                for contestant_id in context.contestant_pages:
                    bg_image_path = await _extract_bg_image(await context.contestant_pages[contestant_id].query_selector("#bg-image"))

                    assert bg_image_path in possible_avatars

                    possible_avatars.remove(bg_image_path)

                assert len(possible_avatars) == len_before - len(contestant_names)

                database.clear_tables(GameContestant, Contestant)
