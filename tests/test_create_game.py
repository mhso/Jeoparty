import pytest

from jeoparty.api.enums import StageType

from tests.browser_context import ContextHandler
from tests.config import PRESENTER_USERNAME, PRESENTER_USER_ID

@pytest.mark.asyncio
async def test_defaults(database):
    pack_name = "Test Pack"
    expected_title = f"{PRESENTER_USERNAME}'s Game"
    expected_password = None
    expected_join_code = f"{PRESENTER_USERNAME.lower()}s_game"
    expected_rounds = 2
    expected_contestants = 4
    expected_doubles = True
    expected_powerups = True
    expected_stage = StageType.LOBBY
    expected_round = 1
    expected_created_by = PRESENTER_USER_ID

    async with ContextHandler(database) as context:
        lobby_page, game_id = await context.create_game(pack_name)

        title_elem = await lobby_page.query_selector("#menu-game-title")

        assert await title_elem.text_content() == expected_title

        game_data = database.get_game_from_id(game_id)

        assert game_data is not None
        assert game_data.pack.name == pack_name
        assert game_data.title == expected_title
        assert game_data.password == expected_password
        assert game_data.join_code == expected_join_code
        assert game_data.regular_rounds == expected_rounds
        assert game_data.max_contestants == expected_contestants
        assert game_data.use_daily_doubles == expected_doubles
        assert game_data.use_powerups == expected_powerups
        assert game_data.stage == expected_stage
        assert game_data.round == expected_round
        assert game_data.created_by == expected_created_by
        assert game_data.get_contestant_with_turn() is None

@pytest.mark.asyncio
async def test_inputs(database):
    pack_name = "Test Pack"
    expected_title = "Jeopardy Extravaganza"
    expected_password = "Pass1337"
    expected_join_code = f"jeopardy_extravaganza"
    expected_rounds = 3
    expected_contestants = 5
    expected_doubles = False
    expected_powerups = True
    expected_stage = StageType.LOBBY
    expected_round = 1
    expected_created_by = PRESENTER_USER_ID

    async with ContextHandler(database) as context:
        lobby_page, game_id = await context.create_game(
            pack_name,
            title=expected_title,
            password=expected_password,
            rounds=expected_rounds,
            contestants=expected_contestants,
            daily_doubles=expected_doubles,
            power_ups=expected_powerups,
        )

        title_elem = await lobby_page.query_selector("#menu-game-title")
        assert await title_elem.text_content() == expected_title

        game_data = database.get_game_from_id(game_id)

        assert game_data is not None
        assert game_data.pack.name == pack_name
        assert game_data.title == expected_title
        assert game_data.password == expected_password
        assert game_data.join_code == expected_join_code
        assert game_data.regular_rounds == expected_rounds
        assert game_data.max_contestants == expected_contestants
        assert game_data.use_daily_doubles == expected_doubles
        assert game_data.use_powerups == expected_powerups
        assert game_data.stage == expected_stage
        assert game_data.round == expected_round
        assert game_data.created_by == expected_created_by

@pytest.mark.asyncio
async def test_errors(database):
    async with ContextHandler(database) as context:
        # Create game with no question pack selected
        page, game_id = await context.create_game()

        assert page.url.split("/")[-1].startswith("create_game")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error: The selected question pack is invalid."

        # Create game with too short of a title
        page, game_id = await context.create_game("Test Pack", "No")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Title' should have at least 3 characters"

        # Create game with a title with invalid characters
        page, game_id = await context.create_game("Test Pack", "Cööl T!tl€")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Title' contains invalid characters"

        # Create game with too short of a password
        page, game_id = await context.create_game("Test Pack", "Game Title", "P")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Password' should have at least 3 characters"

        # Create game with too long of a password
        long_password = "abcdefghijklmn" * 10
        page, game_id = await context.create_game("Test Pack", "Game Title", long_password)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Password' should have at most 64 characters"

        # Create game with too few rounds
        page, game_id = await context.create_game("Test Pack", rounds=0)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Regular rounds' - Input should be greater than 0"

        # Create game with too many rounds
        page, game_id = await context.create_game("Test Pack", rounds=10)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Regular rounds' - Input should be less than 10"

        # Create game with too few contestants
        page, game_id = await context.create_game("Test Pack", contestants=0)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Max contestants' - Input should be greater than 0"

        # Create game with too many contestants
        page, game_id = await context.create_game("Test Pack", contestants=11)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_game_from_id(game_id) is None
        assert await error_elem.text_content() == "Error when creating game: 'Max contestants' - Input should be less than or equal to 10"
