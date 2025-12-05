from glob import glob
import os
import pytest
from sqlalchemy import text

from jeoparty.api.config import Config
from jeoparty.api.orm.models import Contestant
from tests.browser_context import ContextHandler
from tests import create_contestant_data, create_game

# @pytest.mark.asyncio
# async def test_lobby(database):
#     pack_name = "Test Pack"
#     contestant_names, contestant_colors = create_contestant_data()

#     async with ContextHandler(database) as context:
#         with database as session:
#             for theme in ("LAN", "Jul"):
#                 context.contestant_pages.clear()

#                 # Set active theme on the question pack
#                 theme_id = session.execute(text(f"SELECT id FROM themes WHERE name = '{theme}'")).scalar_one()
#                 session.execute(text(f"UPDATE question_packs SET theme_id = '{theme_id}' WHERE name = '{pack_name}'"))
#                 session.commit()

#                 game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, title=f"game_{theme}", daily_doubles=False)
