import asyncio
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from jeoparty.api.orm.models import Game

def create_contestant_data(amount=4):
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
        "Contesto Cinco",
        "Contesto Seis",
        "Contesto Siete",
        "Contesto Ocho",
        "Contesto Nueve",
        "Contesto Diez",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
        "#5A03C4",
        "#EBE807",
        "#FF8000",
        "#1B8524",
        "#00CCFF",
        "#9E9CD6",
    ]

    return contestant_names[:amount], contestant_colors[:amount]

async def create_game(
    context,
    session: Session,
    pack_name: str,
    contestant_names: List[str],
    contestant_colors: List[str],
    join_in_parallel: bool = True,
    **game_params
):
    if "contestants" not in game_params:
        game_params["contestants"] = len(contestant_names)

    game_id = (await context.create_game(pack_name, **game_params))[1]
    game_stmt = select(Game).where(Game.id == game_id)
    game_data = session.execute(game_stmt).scalar_one()

    # Add contestants to the game
    if join_in_parallel:
        async with asyncio.TaskGroup() as group:
            for name, color in zip(contestant_names, contestant_colors): 
                group.create_task(context.join_lobby(game_data.join_code, name, color))

    else:
        for name, color in zip(contestant_names, contestant_colors):
            await context.join_lobby(game_data.join_code, name, color)

    session.refresh(game_data)
    assert len(game_data.game_contestants) == len(contestant_names)

    return game_data
