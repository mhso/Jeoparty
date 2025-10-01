import asyncio
import os
from io import BytesIO
from multiprocessing import Process
from typing import List
from argparse import Namespace

from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, ConsoleMessage
from PIL import Image
from sqlalchemy import Enum

from jeoparty.api.database import Database
from jeoparty.api.enums import Language
from tests.config import PRESENTER_USER_ID, PRESENTER_USERNAME, PRESENTER_PASSWORD
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

BASE_URL = "http://localhost:5006/jeoparty"
PRESENTER_URL = f"{BASE_URL}/presenter"

PRESENTER_VIEWPORT = {"width": 1920, "height": 1080}
CONTESTANT_VIEWPORT = {"width": 428, "height": 926}
PRESENTER_ACTION_KEY = "Space"

class ContextHandler:
    def __init__(self, database: Database, setup_callback=None):
        self.database = database
        self._setup_callback = setup_callback
    
        self.playwright_contexts = []
        self.flask_process = None
        self.presenter_context: BrowserContext = None
        self.presenter_page: Page = None
        self.contestant_contexts: List[BrowserContext] = []
        self.contestant_pages: List[Page] = []
        self._browser_tasks = []

    async def _create_browser(self, context: Playwright):
        return await context.chromium.launch(**BROWSER_OPTIONS)

    async def _login_to_dashboard(self):
        page = await self.presenter_context.new_page()

        await page.goto(BASE_URL)

        name_input = await page.query_selector('input[type="text"]')
        await name_input.fill(PRESENTER_USERNAME)

        password_input = await page.query_selector('input[type="password"]')
        await password_input.fill(PRESENTER_PASSWORD)

        login_btn = await page.query_selector(".login-login-btn")

        async with page.expect_navigation():
            await login_btn.click()

        return page

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
    ):
        if page is None:
            page = self.presenter_page

        await page.goto(f"{BASE_URL}/create_game")

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

        async with page.expect_navigation(wait_until="domcontentloaded"):
            await submit_btn.click()

        return page

    async def create_pack(
        self,
        name: str | None,
        public: bool | None = None,
        finale: bool | None = None,
        language: Language | None = None,
        page: Page | None = None,
    ):
        if page is None:
            page = self.presenter_page

        await page.goto(f"{BASE_URL}/create_pack")

        field_data = [
            ("name", name),
            ("public", public),
            ("include_finale", finale),
            ("language", language),
        ]

        for field, value in field_data:
            if value is None:
                continue

            input_field = await page.query_selector(f"#create-game-{field}")
            if isinstance(value, bool):
                await input_field.set_checked(value)
            elif isinstance(value, Enum):
                await input_field.select_option(value.name, timeout=2000)
            else:
                await input_field.fill(str(value))

        submit_btn = await page.query_selector('input[type="submit"]')

        async with page.expect_navigation(wait_until="domcontentloaded"):
            await submit_btn.click()

        return page

    async def _open_contestant_lobby_page(self, context: BrowserContext, game_id: str, page: Page = None):
        url = f"{BASE_URL}/{game_id}"

        if page is None:
            page = await context.new_page()

        await page.goto(url)
        return page

    async def _join_lobby(self, user_id: int, page: Page):
        name = self._player_names.get(user_id)
        if name is not None:
            # Input player name
            name_input = await page.query_selector("#contestant-lobby-name")
            await name_input.fill(name)

        # Join the lobby
        join_button = await page.query_selector("#contestant-lobby-join")
        await join_button.click()

        # # Wait for the lobby page to load
        # async with page.expect_navigation(url=f"{BASE_URL}/game", wait_until="domcontentloaded"):
        #     pass

    async def _print_console_output(self, msg: ConsoleMessage):
        strings = [str(await arg.json_value()) for arg in msg.args]
        print("Message from console:", " ".join(strings))

    async def _setup_contestant_browser(self, user_id: str):
        if self._setup_callback:
            playwright_context = await async_playwright().__aenter__()
            self.playwright_contexts.append(playwright_context)
        else:
            playwright_context = self.playwright_contexts[0]

        browser = await self._create_browser(playwright_context)
        browser_context = await browser.new_context(viewport=CONTESTANT_VIEWPORT, is_mobile=True, has_touch=True)
        page = await browser_context.new_page()
        page.on("console", self._print_console_output)

        if self._setup_callback:
            await self._setup_callback(user_id, page)

        return browser_context, page

    async def start_game(self):
        reset_questions_btn = await self.presenter_page.query_selector("#menu-buttons > button")
        await reset_questions_btn.click()

        # Plays intro music
        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
        await asyncio.sleep(1.5)
        # Starts the game
        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    async def open_presenter_selection_page(
        self,
        round_num: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[int, int, int, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}?{query_str}")

    async def open_presenter_question_page(
        self,
        round_num: int,
        category: str,
        difficulty: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[int, int, str, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}/{category}/{difficulty}?{query_str}")

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

    async def get_player_scores(self):
        point_elems = await self.presenter_page.query_selector_all(".footer-contestant-entry-score")
        points_text = [await elem.text_content() for elem in point_elems]
        points_values = await self.presenter_page.evaluate("playerScores")

        points_contestants = []
        for page in self.contestant_pages:
            elem = await page.query_selector("#contestant-game-score")
            points_contestants.append(await elem.text_content())

        return points_text, points_values, points_contestants

    async def make_daily_double_wager(self, page: Page, amount: int, dialog_callback=None):
        # Input the amount to wager
        wager_input = await page.query_selector("#question-wager-input")
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

    async def open_endscreen_page(self, player_data: list[tuple[str, int, int, str]]):
        query_str = _get_players_query_string("null", 1, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/endscreen?{query_str}")

    async def screenshot_views(self, index: int = 0):
        width = PRESENTER_VIEWPORT["width"]
        height = PRESENTER_VIEWPORT["height"] + CONTESTANT_VIEWPORT["height"]
        combined_image = Image.new("RGB", (width, height))

        presenter_sc = await self.presenter_page.screenshot(type="png")
        with BytesIO(presenter_sc) as fp:
            presenter_image = Image.open(fp)
            combined_image.paste(presenter_image)

        x = (PRESENTER_VIEWPORT["width"] - CONTESTANT_VIEWPORT["width"] * 4) // 2
        y = PRESENTER_VIEWPORT["height"]
        for contestant_page in self.contestant_pages:
            contestant_sc = await contestant_page.screenshot(type="png")
            with BytesIO(contestant_sc) as fp:
                contestant_image = Image.open(fp)
                combined_image.paste(contestant_image, (x, y))
                x += contestant_image.width

        combined_image.save(f"jeopardy_test_{index}.png")

    async def __aenter__(self):
        self.playwright_contexts = [await async_playwright().__aenter__()]

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

        # Create contestant browsers and contexts
        for user_id in self.database.get_all_contestants():
            if self._setup_callback:
                task = asyncio.create_task(self._setup_contestant_browser(user_id))
                self._browser_tasks.append(task)
            else:
                context, page = await self._setup_contestant_browser(user_id)
                self.contestant_contexts.append(context)
                self.contestant_pages.append(page)

        await asyncio.sleep(1)

        return self

    async def __aexit__(self, *args):
        await self.playwright_contexts[0].stop()

        while any(not task.done() for task in self._browser_tasks):
            await asyncio.sleep(0.1)

        self.flask_process.terminate()
        while self.flask_process.is_alive():
            await asyncio.sleep(0.1)

        self.flask_process.close()
