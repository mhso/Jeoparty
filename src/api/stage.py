from enum import Enum


class Stage(Enum):
    LOBBY = "lobby"
    SELECTION = "selection"
    QUESTION = "question"
    FINALE = "finale"
    ENDED = "ended"
