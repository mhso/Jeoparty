import asyncio
import os
from io import BytesIO
from multiprocessing import Process
import shutil
from typing import Dict, Tuple
from argparse import Namespace

from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, ConsoleMessage
from PIL import Image
from sqlalchemy import Enum

from jeoparty.api.database import Database
from jeoparty.api.enums import Language
from jeoparty.api.config import get_data_path_for_question_pack, get_avatar_path
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

        async def socket_connected():
            return await page.evaluate("socket.connected")

        if not "/create_game" in page.url:
            await self.wait_for_event(socket_connected)

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

        pack_id = page.url.split("/")[-1]
        self.pack_folders.append(pack_id)

        return page, pack_id

    async def _print_console_output(self, msg: ConsoleMessage):
        strings = [str(await arg.json_value()) for arg in msg.args]
        print("Message from console:", " ".join(strings))

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

    async def start_game(self):
        if await self.presenter_page.query_selector("#menu-lobby-music") is not None:
            # Plays intro music
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
            await asyncio.sleep(1.5)

        # Starts the game
        async with self.presenter_page.expect_navigation():
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

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
    ):
        page = self.contestant_pages[contestant_id]

        if color is not None:
            header_elem = await page.query_selector("#contestant-game-header")
            header_style = await header_elem.get_property("style")
            border_color = await header_style.get_property("borderColor")

            assert rgb_to_hex(await border_color.json_value()) == color

        if avatar is not None:
            avatar_elem = await page.query_selector("#contestant-game-avatar")

            src_path = await avatar_elem.get_attribute("src")
            if len(src_path) > len(avatar):
                assert src_path.endswith(avatar)
            elif len(src_path) < len(avatar):
                assert avatar.endswith(src_path)
            else:
                assert src_path == avatar

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
    ):
        game_active = False
        for endpoint in ("question", "selection", "finale"):
            if self.presenter_page.url.endswith(f"/{endpoint}"):
                game_active = True
                break

        if color is not None:
            if game_active:
                wrapper_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
            else:
                wrapper_elem = await self.presenter_page.query_selector(f"#player_{contestant_id}")

            header_style = await wrapper_elem.get_property("style")

            if game_active:
                wrapper_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
                element_color = await header_style.get_property("backgroundColor")
            else:
                wrapper_elem = await self.presenter_page.query_selector(f"#player_{contestant_id}")
                element_color = await header_style.get_property("borderColor")

            assert rgb_to_hex(await element_color.json_value()) == color

        if avatar is not None:
            if game_active:
                wrapper_elem = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
                avatar_elem = await wrapper_elem.query_selector(".footer-contestant-entry-avatar")
            else:
                wrapper_elem = await self.presenter_page.query_selector(f"#player_{contestant_id}")
                avatar_elem = await wrapper_elem.query_selector(".menu-contestant-avatar")

            src_path = await avatar_elem.get_attribute("src")
            if len(src_path) > len(avatar):
                assert src_path.endswith(avatar)
            elif len(src_path) < len(avatar):
                assert avatar.endswith(src_path)
            else:
                assert src_path == avatar

        if has_turn is not None:
            wrapper_element = await self.presenter_page.query_selector(f".footer-contestant-{contestant_id}")
            assert (await wrapper_element.evaluate("(e) => e.classList.contains('active-contestant-entry')")) is has_turn

        if used_power_ups is not None:
            for power_up in used_power_ups:
                wrapper_element = await self.presenter_page.query_selector(f".footer-contestant-power-{power_up}")
                used_icon = await wrapper_element.query_selector(".footer-contestant-entry-power-used")
                assert (used_icon is not None) is used_power_ups[power_up]

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

    async def open_presenter_selection_page(
        self,
        round_num: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[int, int, int, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        await self.presenter_page.goto(f"{ContextHandler.PRESENTER_URL}/{round_num}?{query_str}")

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
        await self.presenter_page.goto(f"{ContextHandler.PRESENTER_URL}/{round_num}/{category}/{difficulty}?{query_str}")

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
        await self.presenter_page.goto(f"{ContextHandler.PRESENTER_URL}/endscreen?{query_str}")

    async def wait_for_event(self, event_func, condition=None, timeout=30):
        time_slept = 0
        sleep_interval = 1
        while time_slept < timeout:
            result = await event_func()
            if (condition is None and result) or (condition is not None and result == condition):
                return

            await asyncio.sleep(sleep_interval)
            time_slept += sleep_interval

        raise TimeoutError("Event never happened!")

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
        for contestant_page in self.contestant_pages.values():
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

        for pack_folder in self.pack_folders:
            shutil.rmtree(get_data_path_for_question_pack(pack_folder), True)

        for avatar_image in self.avatar_images:
            os.remove(f"{get_avatar_path()}/{avatar_image}.png")
