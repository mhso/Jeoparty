from glob import glob
import os
import pytest
from sqlalchemy import text

from jeoparty.api.config import Config
from jeoparty.api.orm.models import Contestant
from tests.browser_context import ContextHandler
from tests import create_contestant_data, create_game

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
                context.contestant_pages.clear()

                # Set active theme on the question pack
                theme_id = session.execute(text(f"SELECT id FROM themes WHERE name = '{theme}'")).scalar_one()
                session.execute(text(f"UPDATE question_packs SET theme_id = '{theme_id}' WHERE name = '{pack_name}'"))
                session.commit()

                game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, title=f"game_{theme}")

                # Assert lobby specific images are correct


                # Assert presenter background image path is correct and that file exists
                bg_image_path = await _extract_bg_image(await context.presenter_page.query_selector(".bg-image"))

                assert bg_image_path == f"data/themes/{theme_id}/presenter_background.jpg"

                possible_backgrounds = set(
                    img.split("static/")[1]
                    for img in glob(f"{Config.STATIC_FOLDER}/data/themes/{theme_id}/contestant_backgrounds/*")
                )
                len_before = len(possible_backgrounds)

                # Assert same for contestant backgrounds
                for contestant_id in context.contestant_pages:
                    bg_image_path = await _extract_bg_image(await context.contestant_pages[contestant_id].query_selector("#bg-image"))

                    assert bg_image_path in possible_backgrounds

                    possible_backgrounds.remove(bg_image_path)

                assert len(possible_backgrounds) == len_before - len(contestant_names)

                if theme == "Jul":
                    avatar_path = f"data/themes/{theme_id}/avatars"
                else:
                    avatar_path = f"img/avatars/default"

                possible_avatars = set(
                    img.split("static/")[1]
                    for img in glob(f"{Config.STATIC_FOLDER}/{avatar_path}/*")
                )
                len_before = len(possible_avatars)

                # Assert contestant avatars are correct
                for contestant in game_data.game_contestants:
                    presenter_avatar = await context.presenter_page.query_selector(f"#player_{contestant.id} > .menu-contestant-avatar")
                    contestant_avatar = await context.contestant_pages[contestant.contestant_id].query_selector("#contestant-game-avatar")

                    for index, avatar in enumerate((presenter_avatar, contestant_avatar)):
                        img_src = await avatar.get_attribute("src")
                        relative_path = img_src.split("static/")[1]

                        assert os.path.exists(f"{Config.STATIC_FOLDER}/{relative_path}")
                        assert relative_path in possible_avatars

                        if index == 1:
                            possible_avatars.remove(relative_path)

                assert len(possible_avatars) == len_before - len(contestant_names)

                database.clear_tables(Contestant)
