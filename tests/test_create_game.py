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
        lobby_page = await context.create_game(pack_name)

        title_elem = await lobby_page.query_selector("#menu-game-title")

        assert await title_elem.text_content() == expected_title

        game_data = database.get_games_for_user(PRESENTER_USER_ID)
        assert len(game_data) == 1

        assert game_data[0].pack.name == pack_name
        assert game_data[0].title == expected_title
        assert game_data[0].password == expected_password
        assert game_data[0].join_code == expected_join_code
        assert game_data[0].regular_rounds == expected_rounds
        assert game_data[0].max_contestants == expected_contestants
        assert game_data[0].use_daily_doubles == expected_doubles
        assert game_data[0].use_powerups == expected_powerups
        assert game_data[0].stage == expected_stage
        assert game_data[0].round == expected_round
        assert game_data[0].created_by == expected_created_by

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
        lobby_page = await context.create_game(
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

        game_data = database.get_games_for_user(PRESENTER_USER_ID)
        assert len(game_data) == 1

        assert game_data[0].pack.name == pack_name
        assert game_data[0].title == expected_title
        assert game_data[0].password == expected_password
        assert game_data[0].join_code == expected_join_code
        assert game_data[0].regular_rounds == expected_rounds
        assert game_data[0].max_contestants == expected_contestants
        assert game_data[0].use_daily_doubles == expected_doubles
        assert game_data[0].use_powerups == expected_powerups
        assert game_data[0].stage == expected_stage
        assert game_data[0].round == expected_round
        assert game_data[0].created_by == expected_created_by

@pytest.mark.asyncio
async def test_errors(database):
    async with ContextHandler(database) as context:
        # Create game with no question pack selected
        page = await context.create_game()

        assert page.url.split("/")[-1].startswith("create_game")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error: The selected question pack is invalid."

        # Create game with too short of a title
        page = await context.create_game("Test Pack", "No")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Title' should have at least 3 characters"

        # Create game with a title with invalid characters
        page = await context.create_game("Test Pack", "Cööl T!tl€")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Title' contains invalid characters"

        # Create game with too short of a password
        page = await context.create_game("Test Pack", "Game Title", "P")

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Password' should have at least 3 characters"

        # Create game with too long of a password
        long_password = "abcdefghijklmn" * 10
        page = await context.create_game("Test Pack", "Game Title", long_password)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Password' should have at most 64 characters"

        # Create game with too few rounds
        page = await context.create_game("Test Pack", rounds=0)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Regular rounds' - Input should be greater than 0"

        # Create game with too many rounds
        page = await context.create_game("Test Pack", rounds=10)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Regular rounds' - Input should be less than 10"

        # Create game with too few contestants
        page = await context.create_game("Test Pack", contestants=0)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Max contestants' - Input should be greater than 0"

        # Create game with too many contestants
        page = await context.create_game("Test Pack", contestants=10)

        error_elem = await page.query_selector("#dashboard-form-error")
        assert database.get_games_for_user(PRESENTER_USER_ID) == []
        assert await error_elem.text_content() == "Error when creating game: Field 'Max contestants' - Input should be less than 10"
