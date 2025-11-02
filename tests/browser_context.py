import asyncio
from glob import glob
import os
import re
import shutil
from io import BytesIO
from multiprocessing import Process
from typing import Dict, List, Tuple
from argparse import Namespace
from contextlib import AsyncExitStack, asynccontextmanager

from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, ConsoleMessage
from PIL import Image
from sqlalchemy import Enum

from jeoparty.api.database import Database
from jeoparty.api.enums import Language
from jeoparty.api.orm.models import GameQuestion
from jeoparty.api.config import get_question_pack_data_path, get_avatar_path
from jeoparty.app.routes.contestant import COOKIE_ID
from tests.config import PRESENTER_USERNAME, PRESENTER_PASSWORD
import main

BROWSER_OPTIONS = {
    "args": [
        "--disable-gl-drawing-for-tests",
        "--hide-scrollbars",
            "--in-process-gpu",
        "--disable-gpu",
        "--no-sandbox",
        "--headless=new",
    ],
    "ignore_default_args": [
        "--enable-automation"
    ],
    "chromium_sandbox": False,
    "headless": True
}

PRESENTER_VIEWPORT = {"width": 1920, "height": 1080}
CONTESTANT_VIEWPORT = {"width": 428, "height": 926}
PRESENTER_ACTION_KEY = "Space"

def _to_hex(r: str):
    hex_num = hex(int(r))
    if hex_num == "0x0":
        return "00"

    return hex_num.removeprefix("0x").upper()

def rgb_to_hex(color: str):
    if color.startswith("rgb"):
        r, g, b = color.removeprefix("rgb(").removesuffix(")").split(",")
        return f"#{_to_hex(r)}{_to_hex(g)}{_to_hex(b)}"

    return color

class ContextHandler:
    BASE_URL = "http://localhost:5006/jeoparty"
    PRESENTER_URL = f"{BASE_URL}/presenter"

    def __init__(self, database: Database):
        self.database = database

        self.playwright_contexts = []
        self.flask_process = None
        self.presenter_context: BrowserContext = None
        self.presenter_page: Page = None
        self.contestant_contexts: Dict[str, BrowserContext] = {}
        self.contestant_pages: Dict[str, Page] = {}
        self.pack_folders = []
        self.avatar_images = []
        self._browser_tasks = []

    async def _create_browser(self, context: Playwright):
        return await context.chromium.launch(**BROWSER_OPTIONS)

    async def _login_to_dashboard(self):
        page = await self.presenter_context.new_page()

        await page.goto(ContextHandler.BASE_URL)

        name_input = await page.query_selector('input[type="text"]')
        await name_input.fill(PRESENTER_USERNAME)

        password_input = await page.query_selector('input[type="password"]')
        await password_input.fill(PRESENTER_PASSWORD)

        login_btn = await page.query_selector(".login-login-btn")

        async with page.expect_navigation():
            await login_btn.click()

        return page

    async def wait_for_event(self, event_func, condition=None, timeout=10):
        time_slept = 0
        sleep_interval = 1
        while time_slept < timeout:
            result = await event_func()
            if (condition is None and result) or (condition is not None and result == condition):
                return

            await asyncio.sleep(sleep_interval)
            time_slept += sleep_interval

        await self.screenshot_views("timeout")

        raise TimeoutError("Event never happened!")

    async def _socket_connected(self):
        status_elem = await self.presenter_page.query_selector("#connection-status")
        return await self.presenter_page.evaluate("socket.connected") and (status_elem is None or await status_elem.is_hidden())

    async def create_game(
        self,
        pack_name: str | None = None,
        title: str | None = None,
        password: str | None = None,
        rounds: int | None = None,
        contestants: int | None = None,
        daily_doubles: bool | None = None,
        power_ups: bool | None = None,
        page: Page | None = None,
    ) -> Tuple[Page, str]:
        if page is None:
            page = self.presenter_page

        await page.goto(f"{ContextHandler.BASE_URL}/create_game")

        field_data = [
            ("title", title),
            ("password", password),
            ("rounds", rounds),
            ("contestants", contestants),
            ("double", daily_doubles),
            ("powers", power_ups)
        ]

        for field, value in field_data:
            if value is None:
                continue

            input_field = await page.query_selector(f"#create-game-{field}")
            if isinstance(value, bool):
                await input_field.set_checked(value)
            else:
                await input_field.fill(str(value))

        if pack_name is not None:
            pack_input = await page.query_selector("#create-game-pack")
            await pack_input.select_option(label=pack_name, timeout=2000)

        submit_btn = await page.query_selector('input[type="submit"]')

        async with page.expect_navigation():
            await submit_btn.click()

        if not "/create_game" in page.url:
            await self.wait_for_event(self._socket_connected)

            game_id = page.url.split("/")[-1]
        else:
            game_id = None

        return page, game_id

    async def create_pack(
        self,
        name: str | None,
        public: bool | None = None,
        finale: bool | None = None,
        language: Language | None = None,
        page: Page | None = None,
    ) -> Tuple[Page, str]:
        if page is None:
            page = self.presenter_page

        await page.goto(f"{ContextHandler.BASE_URL}/create_pack")

        field_data = [
            ("name", name),
            ("public", public),
            ("finale", finale),
            ("language", language),
        ]

        for field, value in field_data:
            if value is None:
                continue

            input_field = await page.query_selector(f"#create-pack-{field}")
            if isinstance(value, bool):
                await input_field.set_checked(value)
            elif isinstance(value, Enum):
                await input_field.select_option(value.value, timeout=2000)
            else:
                await input_field.fill(str(value))

        submit_btn = await page.query_selector('input[type="submit"]')

        async with page.expect_navigation(wait_until="domcontentloaded"):
            await submit_btn.click()

        pack_id = page.url.split("/")[-1].split("#")[0]
        self.pack_folders.append(pack_id)

        return page, pack_id

    async def _print_console_output(self, msg: ConsoleMessage):
        print("Message from console:", msg.text)

    async def _setup_contestant_browser(self):
        playwright_context = self.playwright_contexts[0]

        browser = await self._create_browser(playwright_context)
        browser_context = await browser.new_context(viewport=CONTESTANT_VIEWPORT, is_mobile=True, has_touch=True)
        page = await browser_context.new_page()
        page.on("console", self._print_console_output)

        return browser_context, page

    async def join_lobby(
        self,
        join_code: str,
        name: str | None = None,
        color: str | None = None,
        avatar: str | None = None,
        page: Page | None = None
    ) -> Tuple[Page, str]:
        if page is None:
            contestant_context, contestant_page = await self._setup_contestant_browser()
        else:
            contestant_page = page

        url = f"{ContextHandler.BASE_URL}/{join_code}"
        await contestant_page.goto(url)

        if name is not None:
            # Input player name
            name_input = await contestant_page.query_selector("#contestant-lobby-name")
            await name_input.fill(name)

        if color is not None:
            # Input player color (the hard way because Playwright is no)
            color_input = await contestant_page.query_selector("#contestant-lobby-color")
            await color_input.evaluate(f"(e) => e.value = '{color}'")

        if avatar is not None:
            # Set player avatar
            avatar_input = await contestant_page.query_selector("#contestant-lobby-avatar-input")
            await avatar_input.set_input_files(avatar)

        # Join the lobby
        join_button = await contestant_page.query_selector("#contestant-lobby-join")

        # # Wait for the lobby page to load
        async with contestant_page.expect_navigation(wait_until="domcontentloaded"):
            await join_button.click()

        # Get contestant ID from cookie after they joined the lobby
        cookies = await contestant_page.context.cookies()
        contestant_id = None
        for cookie in cookies:
            if cookie["name"] == COOKIE_ID:
                contestant_id = cookie["value"]
                break

        if contestant_id is None:
            return contestant_page, None

        if avatar is not None:
            self.avatar_images.append(contestant_id)

        if page is None:
            # Safe context and page for contestant
            self.contestant_contexts[contestant_id] = contestant_context
            self.contestant_pages[contestant_id] = contestant_page

        return contestant_page, contestant_id

    @asynccontextmanager
    async def wait_for_event_context_manager(self, event):
        try:
            yield
        finally:
            await self.wait_for_event(event)

    async def wait_until_ready(self):
        """
        Create a stack of context managers so we can wait wait for the presenter
        and each contestant to be redirected after presented jumps to new page.
        Also waits for socket to be ready after navigation has completed.
        """
        stack = AsyncExitStack()

        await stack.enter_async_context(self.wait_for_event_context_manager(self._socket_connected))

        for page in self.contestant_pages.values():
            await stack.enter_async_context(page.expect_navigation())

        await stack.enter_async_context(self.presenter_page.expect_navigation())

        return stack

    async def start_game(self):
        if await self.presenter_page.query_selector("#menu-lobby-music") is not None:
            # Plays intro music
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
            await asyncio.sleep(1.5)

        # Starts the game
        async with await self.wait_until_ready():
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    async def open_selection_page(self, game_id: str):
        url = f"{self.PRESENTER_URL}/{game_id}/selection"
        async with await self.wait_until_ready():
            await self.presenter_page.goto(url)

    async def open_question_page(self, game_id: str):
        url = f"{self.PRESENTER_URL}/{game_id}/question"
        async with await self.wait_until_ready():
            await self.presenter_page.goto(url)

    async def open_endscreen_page(self, player_data: list[tuple[str, int, int, str]]):
        query_str = _get_players_query_string("null", 1, player_data)
        await self.presenter_page.goto(f"{ContextHandler.PRESENTER_URL}/endscreen?{query_str}")

    async def show_question(self, is_daily_double=False):
        if not is_daily_double:
            # Show the question
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        await asyncio.sleep(1)

        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        await asyncio.sleep(0.5)

        # Check if question is multiple choice
        is_multiple_choice = await self.presenter_page.evaluate("() => document.getElementsByClassName('question-choice-entry').length > 0")
        if is_multiple_choice:
            for _ in range(4):
                await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
                await asyncio.sleep(0.5)
        else:
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    async def answer_question(self, index: int | None = None, choice: str | None = None):
        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
        await asyncio.sleep(0.2)
    
        answer_choices = await self.presenter_page.query_selector_all(".question-choices-wrapper > .question-choice-entry")
        if answer_choices != []:
            for i, c in enumerate(answer_choices, start=1):
                text = await c.text_content()
                if text.split(":")[1].strip() == choice:
                    await self.presenter_page.press("body", str(i))
                    break
        else:
            await self.presenter_page.press("body", str(index))

        answer_correct = await self.presenter_page.query_selector("#question-answer-correct")
        answer_wrong = await self.presenter_page.query_selector("#question-answer-wrong")

        async def wait_for_answer():
            return (
                await answer_correct.is_visible()
                or await answer_wrong.is_visible()
            )

        await self.wait_for_event(wait_for_answer)

    async def hit_buzzer(self, contestant_id: str):
        await self.contestant_pages[contestant_id].click("#buzzer-wrapper")

        # Wait for buzz to register on presenter page
        await self.presenter_page.wait_for_selector(".active-contestant-entry")
        await asyncio.sleep(1)

    async def use_power_up(self, contestant_id: str, power_id: str):
        await self.contestant_pages[contestant_id].click(f"#contestant-power-btn-{power_id}")

    async def get_player_scores(self):
        point_elems = await self.presenter_page.query_selector_all(".footer-contestant-entry-score")
        points_text = [await elem.text_content() for elem in point_elems]
        points_values = await self.presenter_page.evaluate("playerScores")

        points_contestants = []
        for page in self.contestant_pages:
            elem = await page.query_selector("#contestant-game-score")
            points_contestants.append(await elem.text_content())

        return points_text, points_values, points_contestants

    async def make_wager(self, contestant_id: str, amount: int, dialog_callback=None):
        page = self.contestant_pages[contestant_id]

        # Input the amount to wager
        wager_input = await page.query_selector(".question-wager-input")
        await wager_input.fill(str(amount))

        async def fail(dialog):
            assert False

        # Handle alert
        if dialog_callback is not None:
            page.on("dialog", dialog_callback)
        else:
            page.on("dialog", fail)

        # Click the submit button
        submit_button = await page.query_selector("#contestant-wager-btn")
        await submit_button.tap()

        async def wager_accepted():
            return await submit_button.evaluate("(e) => e.classList.contains('wager-made')")

        await self.wait_for_event(wager_accepted)

    async def give_finale_answer(self, contestant_id: str, answer: str):
        page = self.contestant_pages[contestant_id]

        # Input the answer
        wager_input = await page.query_selector("#finale-answer")
        await wager_input.fill(answer)

        # Click the submit button
        submit_button = await page.query_selector("#contestant-wager-btn")
        await submit_button.tap()

        async def wager_accepted():
            return await submit_button.evaluate("(e) => e.classList.contains('wager-made')")

        await self.wait_for_event(wager_accepted)

    async def assert_contestant_values(
        self,
        contestant_id: str,
        name: str | None = None,
        color: str | None = None,
        avatar: str | None = None,
        score: int | None = None,
        buzzes: int | None = None,
        hits: int | None = None,
        misses: int | None = None,
        used_power_ups: Dict[str, bool] | None = None,
        enabled_power_ups: Dict[str, bool] | None = None,
    ):
        page = self.contestant_pages[contestant_id]

        # Assert that contestant color is correct
        if color is not None:
            header_elem = await page.query_selector("#contestant-game-header")
            header_style = await header_elem.get_property("style")
            border_color = await header_style.get_property("borderColor")

            assert rgb_to_hex(await border_color.json_value()) == color.upper()

        # Assert that contestant avatar is correct
        if avatar is not None:
            avatar_elem = await page.query_selector("#contestant-game-avatar")

            src_path = await avatar_elem.get_attribute("src")
            if len(src_path) > len(avatar):
                assert src_path.endswith(avatar)
            elif len(src_path) < len(avatar):
                assert avatar.endswith(src_path)
            else:
                assert src_path == avatar

        # Assert that used power-ups are correct
        if used_power_ups is not None:
            for power_up in used_power_ups:
                used_icon = await page.query_selector(f"#contestant-power-btn-{power_up} > .contestant-power-used")
                assert await used_icon.is_visible() is used_power_ups[power_up], f"Correct used {power_up}"

        # Assert that enabled power-ups are correct
        if enabled_power_ups is not None:
            for power_up in enabled_power_ups:
                wrapper_element = await page.query_selector(f"#contestant-power-btn-{power_up}")
                assert await wrapper_element.is_enabled() is enabled_power_ups[power_up], f"Correct enabled {power_up}"

        # Validate remaining fields
        header_data = [
            ("name", name),
            ("score", f"{score} points" if score else None),
            ("buzzes", f"{buzzes} buzzes" if buzzes else None),
            ("hits", str(hits) if hits else None),
            ("misses", str(misses) if misses else None),
        ]

        for elem, value in header_data:
            if value is None:
                continue

            element = await page.query_selector(f"#contestant-game-{elem}")

            assert await element.text_content() == value

    async def assert_presenter_values(
        self,
        contestant_id: str,
        name: str | None = None,
        color: str | None = None,
        avatar: str | None = None,
        score: int | None = None,
        hits: int | None = None,
        misses: int | None = None,
        has_turn: bool | None = None,
        used_power_ups: Dict[str, bool] | None = None,
        ready: bool | None = None,
    ):
        game_active = False
        for endpoint in ("question", "selection", "finale"):
            if self.presenter_page.url.endswith(f"/{endpoint}"):
                game_active = True
                break

        # Assert that contestant color is correct
        if color is not None:
            if game_active:
                wrapper_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
            else:
                wrapper_elem = await self.presenter_page.query_selector(f"#player_{contestant_id}")

            header_style = await wrapper_elem.get_property("style")

            if game_active:
                element_color = await header_style.get_property("backgroundColor")
            else:
                element_color = await header_style.get_property("borderColor")

            assert rgb_to_hex(await element_color.json_value()) == color.upper()

        # Assert that contestant avatar is correct
        if avatar is not None:
            if game_active:
                avatar_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id} > .footer-contestant-entry-avatar")
            else:
                avatar_elem = await self.presenter_page.query_selector(f"#player_{contestant_id} > .menu-contestant-avatar")

            src_path = await avatar_elem.get_attribute("src")
            if len(src_path) > len(avatar):
                assert src_path.endswith(avatar)
            elif len(src_path) < len(avatar):
                assert avatar.endswith(src_path)
            else:
                assert src_path == avatar

        # Assert that contestant having turn is correct
        if has_turn is not None:
            player_turn = await self.presenter_page.eval_on_selector(f".footer-contestant-{contestant_id}", "(e) => e.classList.contains('active-contestant-entry')")
            assert player_turn is has_turn

        # Assert that used power-ups are correct
        if used_power_ups is not None:
            for power_up in used_power_ups:
                wrapper_element = await self.presenter_page.query_selector(f".footer-contestant-power-{power_up}")
                used_icon = await wrapper_element.query_selector(".footer-contestant-entry-power-used")
                assert (used_icon is not None) is used_power_ups[power_up], f"Correct used {power_up}"

        # Assert that ready-state are correct
        if ready is not None:
            ready_icon = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id} > .footer-contestant-entry-ready")
            assert await ready_icon.is_visible() is ready

        # Validate remaining fields
        header_data = [
            ("name", name),
            ("score", f"{score} points" if score else None),
            ("hits", str(hits) if hits else None),
            ("misses", str(misses) if misses else None),
        ]

        for elem, value in header_data:
            if value is None:
                continue

            if game_active:
                wrapper_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
                element = await wrapper_elem.query_selector(f".footer-contestant-entry-{elem}")
            else:
                wrapper_elem = await self.presenter_page.query_selector(f"#player_{contestant_id}")
                element = await wrapper_elem.query_selector(f".menu-contestant-{elem}")

            assert await element.text_content() == value

    async def assert_question_values(
        self,
        question: GameQuestion,
        question_visible: bool | None = True,
        answer_visible: bool | None = None,
        correct_answer: bool | None = None,
        game_feed: List[str] | None = None,
        is_finale: bool = False,
    ):
        # Assert that category header is correct
        expected_category_text = question.question.category.name
        if not is_finale:
            expected_category_text = f"{expected_category_text}for {question.question.value} points"

        category_header = await self.presenter_page.query_selector(".question-category-header")
        assert (await category_header.text_content()).strip() == expected_category_text
        assert await category_header.is_visible()

        # Assert that the question header is correct
        expected_question_text = question.question.question
        question_header = await self.presenter_page.query_selector(".question-question-header")
        assert (await question_header.text_content()).strip() == expected_question_text

        elem_opacity = await question_header.evaluate("(el) => window.getComputedStyle(el).getPropertyValue('opacity')")
        if question_visible is not None:
            assert int(elem_opacity) == int(question_visible)
    
        # Assert that question image is correct if it exists
        if (question_image := question.question.extra.get("question_image")):
            image_elem = await self.presenter_page.query_selector(".question-question-image")

            assert image_elem is not None
            assert (await image_elem.get_attribute("src")).endswith(f"/static/data/{question_image}")

        # Assert that answer image is correct if it exists
        if (answer_image := question.question.extra.get("answer_image")):
            image_elem = await self.presenter_page.query_selector(".question-answer-image")

            assert image_elem is not None
            assert (await image_elem.get_attribute("src")).endswith(f"/static/data/{answer_image}")

        # Assert that question video is correct if it exists
        if (video := question.question.extra.get("video")):
            video_elem = await self.presenter_page.query_selector(".question-question-video")

            assert video_elem is not None
            assert (await video_elem.get_attribute("src")).endswith(f"/static/data/{video}")

        # Assert that question choices are correct if they exist
        if (choices := question.question.extra.get("choices")):
            choice_elems = await self.presenter_page.query_selector_all(".question-choice-entry")
            seen_choices = set()
            for elem in choice_elems:
                choice_text = await elem.text_content()
                seen_choices.add(choice_text.strip().split("\n")[1])

            assert (set(choices).difference(seen_choices)) == set()

        # Assert that tips are correct if they exist
        if (tips := question.question.extra.get("tips")):
            tip_elems = await self.presenter_page.query_selector_all(".question-tip-content")
            seen_tips = set()
            for elem in tip_elems:
                tip_text = await elem.text_content()
                seen_tips.add(tip_text.strip().split("\n")[1])

            assert (set(tips).difference(seen_tips)) == set()

        # Assert that the buzz feed contain correct entries
        if game_feed is not None:
            buzz_feed_elem = await self.presenter_page.query_selector_all("#question-game-feed > ul > li")
            assert len(buzz_feed_elem) == len(game_feed)
            for entry, expected in zip(buzz_feed_elem, game_feed):
                assert re.match(expected, await entry.text_content()) is not None

        # Assert that the answer and explanation is correct
        answer_elem = await self.presenter_page.query_selector("#question-actual-answer > .question-emph")
        answer = await answer_elem.text_content()
        if (explanation := question.question.extra.get("explanation")):
            split = answer.split("(")
            answer = split[0].strip()
            explanation_text = split[1].removesuffix(")").strip()
            assert explanation_text == explanation

        assert answer == f"'{question.question.answer}'"
        if answer_visible is not None:
            assert await answer_elem.is_visible() is answer_visible

        if correct_answer is not None:
            if correct_answer:
                correct_elem = await self.presenter_page.query_selector("#question-answer-correct")
                assert await correct_elem.is_visible()
            else:
                wrong_elem = await self.presenter_page.query_selector("#question-answer-wrong")
                assert await wrong_elem.is_visible()

    async def assert_finale_wager_values(
        self,
        locale: Dict[str, str],
        round_name: str = "Final Jeoparty!",
        category_name: str | None = None,
        music_playing: bool = False
    ):
        round_header = await self.presenter_page.query_selector("#selection-finale-wrapper > h1")
        sub_header_1 = await self.presenter_page.query_selector("#selection-finale-header1")
        sub_header_2 = await self.presenter_page.query_selector("#selection-finale-header2")
        sub_header_3 = await self.presenter_page.query_selector("#selection-finale-header3")

        assert await round_header.text_content() == round_name

        if category_name is None:
            assert await sub_header_1.evaluate("(e) => e.style.opacity == 0")
        else:
            assert await sub_header_1.evaluate("(e) => e.style.opacity == 1")
            assert await sub_header_1.text_content() == locale["finale_reveal_1"]
            assert await sub_header_2.text_content() == category_name
            assert await sub_header_3.text_content() == locale["finale_reveal_2"]

        music = await self.presenter_page.query_selector("#selection-jeopardy-theme")
        assert await music.evaluate("(elem) => elem.paused") is not music_playing

    async def screenshot_views(self, suffix: str | None = None):
        width = PRESENTER_VIEWPORT["width"]
        height = PRESENTER_VIEWPORT["height"] + CONTESTANT_VIEWPORT["height"]
        combined_image = Image.new("RGB", (width, height))

        presenter_sc = await self.presenter_page.screenshot(type="png")
        with BytesIO(presenter_sc) as fp:
            presenter_image = Image.open(fp)
            combined_image.paste(presenter_image)

        border_width = 2
        x = ((PRESENTER_VIEWPORT["width"] - CONTESTANT_VIEWPORT["width"] * 4) // 2) - (border_width * 4)
        y = PRESENTER_VIEWPORT["height"]
        for contestant_page in self.contestant_pages.values():
            contestant_sc = await contestant_page.screenshot(type="png")
            with BytesIO(contestant_sc) as fp:
                contestant_image = Image.open(fp)
                combined_image.paste(contestant_image, (x, y))
                x += contestant_image.width + border_width

        if not suffix:
            suffix = "0"

        combined_image.save(f"jeoparty_test_{suffix}.png")

    async def __aenter__(self):
        self.playwright_contexts = [await async_playwright().__aenter__()]

        old_screenshots = glob("jeoparty_test_*.png")
        for screenshot in old_screenshots:
            os.remove(screenshot)

        cwd = os.getcwd()
        new_cwd = os.path.join(cwd, "src")
        os.chdir(new_cwd)

        self.flask_process = Process(target=main.run_app, args=(Namespace(database="test.db"),))
        self.flask_process.start()

        os.chdir(cwd)

        # Create presenter browser and context
        presenter_browser = await self._create_browser(self.playwright_contexts[0])
        self.presenter_context = await presenter_browser.new_context(viewport=PRESENTER_VIEWPORT)

        self.presenter_page = await self._login_to_dashboard()
        self.presenter_page.on("console", self._print_console_output)

        await asyncio.sleep(1)

        return self

    async def __aexit__(self, *args):
        while any(not task.done() for task in self._browser_tasks):
            await asyncio.sleep(0.1)

        self.flask_process.terminate()
        while self.flask_process.is_alive():
            await asyncio.sleep(0.1)

        self.flask_process.close()

        await self.presenter_context.browser.close()
        await self.playwright_contexts[0].stop()

        for pack_folder in self.pack_folders:
            shutil.rmtree(get_question_pack_data_path(pack_folder), True)

        for avatar_image in self.avatar_images:
            os.remove(f"{get_avatar_path()}/{avatar_image}.png")
