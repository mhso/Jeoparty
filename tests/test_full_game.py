import asyncio
import math
import random
from typing import Dict, List

import pytest
from playwright.async_api import Page

from jeoparty.api.enums import PowerUpType, StageType
from jeoparty.api.orm.models import Game
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY
from tests import create_contestant_data, create_game

async def handle_selection_page(context: ContextHandler, game_data: Game):
    # Choose random question from the ones remaining
    unused_questions = [question for question in game_data.get_questions_for_round() if not question.used]
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
                    async with await context.wait_until_ready():
                        await question_elem.click()

                    return

    assert False, "Could not find active question in selection"

async def answer_question(context, contestant, question, guessed_choices):
    # Answer correctly or wrong randomly
    if question.question.extra and question.question.extra.get("choices"):
        remaining_choices = [choice for choice in question.question.extra["choices"] if choice not in guessed_choices]
        choice = random.choice(remaining_choices)
        guessed_choices.add(choice)
        correct = choice == question.question.answer
        print(f"Answering choice '{choice}'")
        await context.answer_question(contestant.contestant_id, choice=choice)
    else:
        key = random.randint(1, 2)
        print(f"Answering key '{key}'")
        correct = key == 1
        await context.answer_question(contestant.contestant_id, key=key)

    return correct

async def handle_question_page(context: ContextHandler, game_data: Game, locale: Dict[str, str]):
    active_question = game_data.get_active_question()
    active_contestant = game_data.get_contestant_with_turn()

    assert active_question is not None
    assert active_contestant is not None

    if active_question.question.extra and active_question.question.extra.get("choices"):
        assert active_question.question.answer in active_question.question.extra["choices"]

    contestants_with_hijack = [
        contestant for contestant in game_data.game_contestants
        if not contestant.get_power(PowerUpType.HIJACK).used
    ]

    hijack_player = None
    if active_question.daily_double:
        # Make a random wager
        wager = random.randint(100, max(500 * game_data.round, active_contestant.score))
        await context.make_wager(active_contestant.contestant_id, wager)
        max_buzz_attempts = 1
    elif contestants_with_hijack != [] and random.random() < 0.2:
        # Have someone use hijack before the question is asked
        hijack_player = random.choice(contestants_with_hijack)
        await context.use_power_up(hijack_player.contestant_id, PowerUpType.HIJACK.value)
        await asyncio.sleep(2)

        max_buzz_attempts = 1
    else:
        max_buzz_attempts = game_data.max_contestants

    await context.show_question()

    if not hijack_player and not active_question.daily_double and contestants_with_hijack != [] and random.random() < 0.2:
        # Have someone hijack after the question is asked
        hijack_player = random.choice(contestants_with_hijack)
        await context.use_power_up(hijack_player.contestant_id, PowerUpType.HIJACK.value)
        await asyncio.sleep(2)

        max_buzz_attempts = 1

    video = await context.presenter_page.query_selector(".question-question-video")
    guessed_choices = set()
    players_buzzed = set()

    for _ in range(max_buzz_attempts):
        if hijack_player:
            await context.hit_buzzer(hijack_player.contestant_id)
            buzz_winner = hijack_player
        elif active_question.daily_double:
            buzz_winner = active_contestant
        else:
            # Choose one or more random players to answer
            question = await context.presenter_page.query_selector(".question-question-header")
            min_val = 0 if video is None and await question.is_visible() else 1
            num_players = math.ceil(random.randint(min_val, game_data.max_contestants * 6) / 6)

            if num_players == 0: # No one buzzes in and time runs out
                await asyncio.sleep(active_question.question.category.buzz_time + 3)
                break

            shuffled_players = [
                contestant for contestant in game_data.game_contestants
                if contestant.id not in players_buzzed
            ]
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

        players_buzzed.add(buzz_winner.id)

        await asyncio.sleep(1)

        # Randomly use freeze if available
        if not active_question.daily_double:
            freeze_power = buzz_winner.get_power(PowerUpType.FREEZE)
            if not freeze_power.used and random.random() < 0.3:
                await context.use_power_up(buzz_winner.contestant_id, freeze_power.type.value)
                await asyncio.sleep(3)

        # Answer correctly or wrong randomly
        correct = await answer_question(context, buzz_winner, active_question, guessed_choices)

        await asyncio.sleep(1)

        # Randomly use rewind if available and answer again
        if not active_question.daily_double:
            rewind_power = buzz_winner.get_power(PowerUpType.REWIND)
            if not correct and not rewind_power.used and random.random() < 0.5:
                await context.use_power_up(buzz_winner.contestant_id, rewind_power.type.value)

                await asyncio.sleep(2)

                correct = await answer_question(context, buzz_winner, active_question, guessed_choices)
                await asyncio.sleep(2)

        if correct:
            break

    await asyncio.sleep(1)

    async with await context.wait_until_ready():
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

async def handle_finale_wager_page(context: ContextHandler, game_data: Game):
    # Wait for category to be revealed
    await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
    await asyncio.sleep(4)

    wagers = []
    for contestant in game_data.game_contestants:
        # Get a random wager for each contestant
        if random.random() < 0.1:
            wager = 0
        else:
            wager = random.randint(1, max(1000, contestant.score))

        wagers.append((contestant, wager))

    # Make the wagers in parallel to stress-test
    pending = (
        await asyncio.wait(
            [
                asyncio.create_task(context.make_wager(contestant.contestant_id, wager))
                for contestant, wager in wagers
            ],
            timeout=10
        )
    )[1]

    assert len(pending) == 0

    await asyncio.sleep(1)

    # Go to finale question page
    async with await context.wait_until_ready():
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)    

async def handle_finale_question_page(context: ContextHandler, game_data: Game):
    assert game_data.round == game_data.regular_rounds + 1
    assert len(game_data.get_questions_for_round()) == 1

    await context.show_question()

    possible_answers = [
        "1", "two", "3", "4", "four", "none", "zero", "idk", "who cares?"
    ]

    answers = []
    for contestant in game_data.game_contestants:
        # Get a random answer for each contestant
        if contestant.finale_wager:
            answers.append((contestant, random.choice(possible_answers)))

    # Give the answers in parallel to stress-test
    pending = (
        await asyncio.wait(
            [
                asyncio.create_task(context.give_finale_answer(contestant.contestant_id, answer))
                for contestant, answer in answers
            ],
            timeout=10
        )
    )[1]

    assert len(pending) == 0

    await asyncio.sleep(2)

    # Finish the question and go to finale screen
    async with context.presenter_page.expect_navigation(timeout=5000):
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

async def handle_finale_result_page(context: ContextHandler, game_data: Game):
    await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

    await asyncio.sleep(0.5)

    for contestant in game_data.game_contestants:
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

        await asyncio.sleep(0.5)

        if contestant.finale_answer:
            correct = contestant.finale_answer in ("4", "four")
            if correct:
                key = "1"
            else:
                key = "2"
        else:
            key = "1"

        await context.presenter_page.press("body", key)

        await asyncio.sleep(1)

    await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

    await asyncio.sleep(1)

    await context.presenter_page.wait_for_url("**/endscreen", timeout=10000)

async def handle_endscreen_page(context: ContextHandler):
    # Play confetti video
    await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

    await asyncio.sleep(5)

def to_absolute_url(page: Page, url: str):
    http_split = page.url.split("://")
    base_url = http_split[0] + "://" + http_split[1].split("/")[0]

    if url.startswith("/"):
        return f"{base_url}{url}"

    return url

async def get_all_links(page: Page) -> List[str]:
    links = await page.locator("a").all()
    media = (
        (await page.locator("img").all()) +
        (await page.locator("video > source").all()) +
        (await page.locator("audio > source").all())
    )

    all_tasks = []
    async with asyncio.TaskGroup() as group:
        for elem in links:
            all_tasks.append(group.create_task(elem.get_attribute("href")))

    async with asyncio.TaskGroup() as group:
        for elem in media:
            all_tasks.append(group.create_task(elem.get_attribute("src")))

    return [to_absolute_url(page, task.result()) for task in all_tasks]

async def get_broken_links(page: Page, links: List[str]) -> List[str]:
    request_tasks = []
    async with asyncio.TaskGroup() as group:
        for url in links:
            request_tasks.append((url, group.create_task(page.request.get(url))))

    broken_links = []
    for url, task in request_tasks:
        response = task.result()
        if not response.ok:
            broken_links.append(url)

    return broken_links

async def validate_links(context: ContextHandler):
    broken_links = []
    for page in [context.presenter_page] + list(context.contestant_pages.values()):
        all_links = await get_all_links(page)
        broken_links.extend(await get_broken_links(page, all_links))

    assert broken_links == [], f"There are {len(broken_links)} broken links"

    return broken_links

@pytest.mark.asyncio
async def test_random_game(database, locales):
    pack_name = "Julequiz 2025"
    rounds = 1 if pack_name == "Julequiz 2025" else 2
    seed = 1337
    random.seed(seed)

    num_contestants = 4
    contestant_names, contestant_colors = create_contestant_data(num_contestants)

    async with ContextHandler(database, True) as context:
        with database as session:
            # Create game with 3-10 contestants randomly chosen
            game_data = await create_game(context, session, pack_name, contestant_names, contestant_colors, rounds=rounds)
            locales = locales[game_data.pack.language.value]["pages"]

            await asyncio.sleep(1)

            await context.start_game()
            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            async def first_turn_chosen():
                return await context.presenter_page.evaluate("playerTurn != null")

            await context.wait_for_event(first_turn_chosen, timeout=60)

            intro_media = await context.presenter_page.query_selector("#selection-intro-media")
            async def intro_media_done():
                return intro_media is None or await intro_media.evaluate("(e) => e.ended")

            await context.wait_for_event(intro_media_done, timeout=30)

            await asyncio.sleep(1)

            curr_round = game_data.round
            questions_in_round = len(game_data.get_questions_for_round())
            question_index = 0

            while True:
                session.refresh(game_data)

                await validate_links(context)

                match game_data.stage:
                    case StageType.SELECTION:
                        print("=" * 30, "SELECTION", "=" * 30)
                        if question_index == questions_in_round:
                            assert game_data.round == curr_round + 1
                            questions_in_round = len(game_data.get_questions_for_round())
                            question_index = 0

                        await handle_selection_page(context, game_data)
                    case StageType.QUESTION:
                        print("=" * 30, "QUESTION", "=" * 30)
                        await handle_question_page(context, game_data, locales["presenter/question"])
                    case StageType.FINALE_WAGER:
                        print("=" * 30, "FINALE WAGER", "=" * 30)
                        await handle_finale_wager_page(context, game_data)
                    case StageType.FINALE_QUESTION:
                        print("=" * 30, "FINALE QUESTION", "=" * 30)
                        await handle_finale_question_page(context, game_data)
                    case StageType.FINALE_RESULT:
                        print("=" * 30, "FINALE RESULT", "=" * 30)
                        await handle_finale_result_page(context, game_data)
                    case StageType.ENDED:
                        print("=" * 30, "ENDSCREEN", "=" * 30)
                        await handle_endscreen_page(context)
                        return
