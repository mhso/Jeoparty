import pytest

from jeoparty.api.enums import StageType

from tests.browser_context import ContextHandler
from tests.config import PRESENTER_USERNAME, PRESENTER_USER_ID

@pytest.mark.asyncio
async def test_create_pack_defaults(database):
    pack_name = "Pack-a-doodle-doo"
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
        pack_page = await context.create_pack(pack_name)

        
