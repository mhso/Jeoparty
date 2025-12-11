import asyncio
import pytest

from jeoparty.api.enums import StageType
from tests.browser_context import ContextHandler, PRESENTER_ACTION_KEY

@pytest.mark.asyncio
async def test_finale_result(database, locales):
    pack_name = "Test Pack"
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
    ]
    contestant_buzzes = [5, 9, 3, 1]
    contestant_hits = [3, 6, 1, 0]
    contestant_misses = [2, 3, 2, 1]

    async with ContextHandler(database, True) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database:
            game_data = database.get_game_from_id(game_id)
            language_locale = locales[game_data.pack.language.value]
            locale = language_locale["pages"]["presenter/endscreen"]
            locale.update(language_locale["pages"]["global"])

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            game_data.round = 3
            game_data.stage = StageType.ENDED

            database.save_models(game_data)

            assert len(game_data.game_contestants) == len(contestant_names)

            # Create an endscreen with one winner
            contestant_scores = [500, 600, 500, 0]
            for contestant, score, buzzes, hits, misses in zip(
                game_data.game_contestants,
                contestant_scores,
                contestant_buzzes,
                contestant_hits,
                contestant_misses
            ):
                contestant.score = score
                contestant.buzzes = buzzes
                contestant.hits = hits
                contestant.misses = misses

            database.save_models(*game_data.game_contestants)

            await context.open_endscreen_page(game_data.id)

            expected_winner_desc = f"{contestant_names[1]} {locale['winner_flavor_1']}"
            await context.assert_endscreen_values(
                locale, expected_winner_desc, game_data.game_contestants
            )

            # Create an endscreen with two winners
            contestant_scores = [500, 600, 600, 0]
            for contestant, score in zip(
                game_data.game_contestants, contestant_scores
            ):
                contestant.score = score

            database.save_models(*game_data.game_contestants)

            await context.open_endscreen_page(game_data.id)

            expected_winner_desc = (
                f"{contestant_names[1]} {locale['and']} {contestant_names[2]} {locale['winner_flavor_2']}"
            )
            await context.assert_endscreen_values(
                locale, expected_winner_desc, game_data.game_contestants
            )

            # Create an endscreen with three winners
            contestant_scores = [600, 600, 600, 100]
            for contestant, score in zip(
                game_data.game_contestants, contestant_scores
            ):
                contestant.score = score

            database.save_models(*game_data.game_contestants)

            await context.open_endscreen_page(game_data.id)

            expected_winner_desc = (
                f"{contestant_names[1]}, {contestant_names[2]}, {locale['and']} "
                f"{contestant_names[0]} {locale['winner_flavor_3']}"
            )
            await context.assert_endscreen_values(
                locale, expected_winner_desc, game_data.game_contestants
            )

            # Start the endscreen party!
            await asyncio.sleep(1)
            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            # Stop the party after three seconds
            await asyncio.sleep(3)

            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
            await asyncio.sleep(1)
