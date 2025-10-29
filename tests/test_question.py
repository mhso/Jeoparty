import pytest

from jeoparty.api.enums import StageType
from tests.browser_context import ContextHandler

@pytest.mark.asyncio
async def test_question_view_first_round(database, locales):
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

    async with ContextHandler(database) as context:
        game_id = (await context.create_game(pack_name, daily_doubles=False))[1]

        with database as session:
            game_data = database.get_game_from_id(game_id)
            locale = locales[game_data.pack.language.value]["pages"]["presenter/question"]

            # Add contestants to the game
            for name, color in zip(contestant_names, contestant_colors):
                await context.join_lobby(game_data.join_code, name, color)

            await context.start_game()

            session.refresh(game_data)

            # Set player 1 as having the turn and question 1 as the active question
            active_player = next(filter(lambda c: c.contestant.name == contestant_names[0], game_data.game_contestants))
            active_question = next(filter(lambda q: q.question.extra and q.question.extra.get("choices"), game_data.game_questions))

            active_player.has_turn = True
            active_question.active = True

            database.save_models(active_player, active_question)

            await context.open_question_page(game_data.id)
            session.refresh(game_data)

            # Assert that initial values contestant/presenter values are correct
            assert game_data.stage == StageType.QUESTION

            for contestant, name, color in zip(game_data.game_contestants, contestant_names, contestant_colors):
                assert contestant.power_ups != []

                await context.assert_contestant_values(
                    contestant.contestant_id,
                    name,
                    color,
                    score=0,
                    buzzes=0,
                    hits=0,
                    misses=0,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                    enabled_power_ups={"hijack": True, "freeze": False, "rewind": False},
                )

                await context.assert_presenter_values(
                    contestant.id,
                    name,
                    color,
                    score=0,
                    hits=0,
                    misses=0,
                    has_turn=False,
                    used_power_ups={"hijack": False, "freeze": False, "rewind": False}
                )

            # Assert that the question view elements are correct
            await context.assert_question_values(
                active_question,
                question_visible=False,
                answer_visible=False,
            )

            await context.show_question()

            await context.assert_question_values(
                active_question,
                question_visible=True,
                answer_visible=False,
            )

            # Let a player buzz in
            buzz_player = next(filter(lambda c: c.contestant.name == contestant_names[2], game_data.game_contestants))
            await context.hit_buzzer(buzz_player.contestant_id)

            await context.assert_contestant_values(
                buzz_player.contestant_id,
                contestant_names[2],
                contestant_colors[2],
                score=0,
                buzzes=0, # Buzzes only update on page refresh, so here it's still 0
                hits=0,
                misses=0,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": True, "freeze": True, "rewind": False},
            )

            await context.assert_presenter_values(
                buzz_player.id,
                buzz_player.contestant.name,
                buzz_player.contestant.color,
                score=0,
                hits=0,
                misses=0,
                has_turn=True,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )

            await context.assert_question_values(
                active_question,
                True,
                False,
                game_feed=[f"{contestant_names[2]} {locale['game_feed_buzz_1']} " + r"\d{1,3}\.\d{2} " + locale['game_feed_buzz_2']]
            )

            # Have the player answer the question wrong
            await context.answer_question(choice="Eggs")

            await context.assert_contestant_values(
                buzz_player.contestant_id,
                contestant_names[2],
                contestant_colors[2],
                score=0,
                buzzes=0,
                hits=0,
                misses=0, # Misses only update on page refresh, so here it's still 0
                used_power_ups={"hijack": False, "freeze": False, "rewind": False},
                enabled_power_ups={"hijack": False, "freeze": False, "rewind": True},
            )

            await context.assert_presenter_values(
                buzz_player.id,
                buzz_player.contestant.name,
                buzz_player.contestant.color,
                score=-active_question.question.value,
                hits=0,
                misses=0, # Misses only update on page refresh, so here it's still 0
                has_turn=False,
                used_power_ups={"hijack": False, "freeze": False, "rewind": False}
            )
