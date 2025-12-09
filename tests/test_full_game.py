import asyncio
import random
from typing import Dict

from jeoparty.api.enums import StageType
import pytest
from sqlalchemy import text

from jeoparty.api.config import Config
from jeoparty.api.orm.models import Contestant, Game
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY
from tests import create_contestant_data, create_game

async def handle_selection_page(context: ContextHandler, game_data: Game):
    # Choose random question from the ones remaining
    unused_questions = [question for question in game_data.game_questions if not question.used]
    active_question = random.choice(unused_questions)
    category_name = active_question.question.category.name

    category_wrappers = await context.presenter_page.query_selector_all(".selection-category-entry")
    for category_wrapper in category_wrappers:
        header = await category_wrapper.query_selector(".selection-category-header > span")
        if (await header.text_content()).strip() == category_name:
            question_elements = await category_wrapper.query_selector_all(".selection-question-box")
            for question_elem in question_elements:
                if (await question_elem.text_content()).strip() == str(active_question.question.value):
                    assert not await question_elem.evaluate("(e) => e.classList.contains('inactive')"), "Question is already used"
                    await question_elem.click()

    assert False, "Could not find active question in selection"

async def handle_question_page(context: ContextHandler, game_data: Game, locale: Dict[str, str]):
    active_question = game_data.get_active_question()
    assert active_question is not None

    await context.show_question(active_question.daily_double)

    # Choose one or more random players to answer
    num_players = random.randint(0, game_data.max_contestants * 4) // 4

    if num_players == 0: # No one buzzes in and time runs out
        await asyncio.sleep(active_question.question.category.buzz_time + 1)
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
        return

    shuffled_players = list(game_data.game_contestants)
    random.shuffle(shuffled_players)
    players_buzzing = shuffled_players[:num_players]

    # Try to buzz in at the same time
    pending = (
        await asyncio.wait(
            [
                asyncio.create_task(context.hit_buzzer(contestant.contestant_id))
                for contestant in players_buzzing
            ],
            timeout=10
        )
    )[1]

    assert len(pending) == 0

    buzz_winner = (await context.find_buzz_winner(game_data.game_contestants, locale))[0]

    for _ in range(game_data.max_contestants):
        # Answer correctly or wrong randomly
        if "choices" in active_question.question.extra:
            choice = random.choice(active_question.question.extra["choices"])
            correct = choice == active_question.question.answer
            await context.answer_question(buzz_winner.contestant_id, choice=choice)
        else:
            key = random.randint(1, 2)
            correct = key == 1
            await context.answer_question(buzz_winner.contestant_id, key=key)

        if correct:
            break

    await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

@pytest.mark.asyncio
async def test_random_game(database, locales):
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
                locales = locales[game_data.pack.language.value]["pages"]

                await context.start_game()
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

                async def first_turn_chosen():
                    return await context.presenter_page.evaluate("playerTurn != null")

                await context.wait_for_event(first_turn_chosen)

                await asyncio.sleep(1)

                while True:
                    session.refresh(game_data)

                    match game_data.stage:
                        case StageType.SELECTION:
                            await handle_selection_page(context, game_data)
                        case StageType.QUESTION:
                            await handle_question_page(context, game_data, locales["presenter/question"])
                        case StageType.ENDED:
                            break

                database.clear_tables(Contestant)
