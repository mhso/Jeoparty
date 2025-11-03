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
    contestant_scores = [
        -500, 300, 1200, 0
    ]
    contestant_wagers = [1000, 300, 700, 0]
    contestant_answers = ["4", "4", "3", None]

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            language_locale = locales[game_data.pack.language.value]
            locale = language_locale["pages"]["presenter/finale"]
            locale.update(language_locale["pages"]["global"])

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            game_data.round = 3
            game_data.stage = StageType.FINALE_RESULT
            finale_question = game_data.get_questions_for_round()[0]
            finale_question.active = True

            database.save_models(finale_question, game_data)

            assert len(game_data.game_contestants) == len(contestant_names)

            for contestant, score, wager, answer in zip(
                game_data.game_contestants,
                contestant_scores,
                contestant_wagers,
                contestant_answers
            ):
                contestant.score = score
                contestant.finale_wager = wager
                contestant.finale_answer = answer

            database.save_models(*game_data.game_contestants)

            await context.open_finale_page(game_data.id)
            await context.wait_for_event(context._socket_connected)

            session.refresh(game_data)

            # Show results
            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            await asyncio.sleep(0.5)

            lines = []
            for contestant in game_data.game_contestants:
                wager = contestant.finale_wager or locale["nothing"]

                answer = locale["nothing"] if not contestant.finale_wager else f"'{contestant.finale_answer}'"
                lines.append([f"{contestant.contestant.name} {locale['player_answer']} {answer}"])

                await context.assert_finale_result_values(locale, lines)
                await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

                await asyncio.sleep(0.25)

                if contestant.finale_answer is not None:
                    correct = contestant.finale_answer == "4"
                    if correct:
                        correct_line = f"{locale['answer_correct_1']} {locale['answer_correct_2']}"
                        key = "1"
                    else:
                        correct_line = f"{locale['answer_wrong_1']} {locale['answer_wrong_2']}"
                        key = "2"

                    result_line = f"{correct_line} {wager} {locale['points']}!"
                else:
                    result_line = locale["answer_skipped"]

                lines[-1].append(result_line)

                await context.presenter_page.press("body", key)

                await context.assert_finale_result_values(locale, lines)

                await asyncio.sleep(0.25)

            await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            await asyncio.sleep(1)

            await context.assert_finale_result_values(locale, lines, True)

            await context.presenter_page.wait_for_url("**/endscreen", timeout=10000)

            session.refresh(game_data)

            # Assert final values
            expected_scores = [500, 600, 500, 0]
            for contestant, expected_score in zip(game_data.game_contestants, expected_scores):
                assert contestant.score == expected_score

            assert game_data.stage == StageType.ENDED
