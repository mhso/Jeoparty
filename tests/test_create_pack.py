import os
import pytest
from sqlalchemy import text

from jeoparty.api.enums import Language
from jeoparty.api.config import get_question_pack_data_path

from tests.browser_context import ContextHandler
from tests.config import PRESENTER_USER_ID

@pytest.mark.asyncio
async def test_create_pack_defaults(database):
    expected_name = "Pack-a-doodle-doo"
    expected_public = False
    expected_finale = True
    expected_language = Language.ENGLISH
    expected_round_1_short = "Round 1"
    expected_round_2_short = "Finale"
    expected_round_1_long = "Jeoparty!"
    expected_round_2_long = "Final Jeoparty!"

    with database as session:
        session.execute(text("DELETE FROM question_packs"))
        session.commit()

    async with ContextHandler(True) as context:
        pack_page, pack_id = await context.create_pack(expected_name)

        title_elem = await pack_page.query_selector("#question-pack-name")
        assert await title_elem.input_value() == expected_name

        public_elem = await pack_page.query_selector("#question-pack-public")
        assert await public_elem.is_checked() is expected_public

        finale_elem = await pack_page.query_selector("#question-pack-finale")
        assert await finale_elem.is_checked() is expected_finale

        language_elem = await pack_page.query_selector("#question-pack-language")
        assert await language_elem.input_value() == expected_language.value

        round_select_btns = await pack_page.query_selector_all(".question-pack-round-select-button")

        assert len(round_select_btns) == 2

        assert await round_select_btns[0].text_content() == expected_round_1_short
        assert await round_select_btns[1].text_content() == expected_round_2_short

        round_wrappers = await pack_page.query_selector_all(".question-pack-round-wrapper")

        assert len(round_wrappers) == 2

        round_1_title = await round_wrappers[0].query_selector(".question-pack-round-name")
        assert await round_1_title.input_value() == expected_round_1_long

        category_placeholder_1 = await round_wrappers[0].query_selector(".question-pack-categories-placeholder")

        assert await category_placeholder_1.is_visible()
        assert (await category_placeholder_1.text_content()).strip() == "Add a Category"

        await round_select_btns[1].click()

        round_2_title = await round_wrappers[1].query_selector(".question-pack-round-name")
        assert await round_2_title.input_value() == expected_round_2_long

        category_placeholder_2 = await round_wrappers[1].query_selector(".question-pack-categories-placeholder")

        assert await category_placeholder_2.is_visible()
        assert (await category_placeholder_2.text_content()).strip() == "Add Finale Question"

        pack_data = database.get_question_packs_for_user(PRESENTER_USER_ID, pack_id)

        assert pack_data is not None
        assert pack_data.name == expected_name
        assert pack_data.public is expected_public
        assert pack_data.include_finale is expected_finale
        assert pack_data.language is expected_language

        assert os.path.exists(get_question_pack_data_path(pack_data.id))
