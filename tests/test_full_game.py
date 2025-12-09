import random
import os
from glob import glob

import pytest
from sqlalchemy import text

from jeoparty.api.config import Config
from jeoparty.api.orm.models import Contestant
from tests.browser_context import ContextHandler
from tests import create_contestant_data, create_game

async def choose_unused_question():
    pass



@pytest.mark.asyncio
async def test_random_game(database):
    pack_name = "Test Pack"
    num_contestants = random.randint(3, 10)
    contestant_names, contestant_colors = create_contestant_data(num_contestants)

    async with ContextHandler(database) as context:
        with database as session:
            for theme in ("LAN", "Jul"):
                context.contestant_pages.clear()

                # Set active theme on the question pack
                theme_id = session.execute(text(f"SELECT id FROM themes WHERE name = '{theme}'")).scalar_one()
                session.execute(text(f"UPDATE question_packs SET theme_id = '{theme_id}' WHERE name = '{pack_name}'"))
                session.commit()

                # Create game with 3-10 contestants randomly chosen
                game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, title=f"game_{theme}")

                await context.start_game()
                session.refresh(game_data)

                while True:
                    # Choose random question from the ones remaining
                    unused_questions = [question for question in game_data.game_questions if not question.used]
                    break

                database.clear_tables(Contestant)
