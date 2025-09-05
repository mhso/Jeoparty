from enum import Enum


class Stage(Enum):
    LOBBY = "lobby"
    SELECTION = "selection"
    QUESTION = "question"
    FINALE_WAGER = "finale_wager"
    FINALE_QUESTION = "finale_question"
    FINALE_RESULT = "finale_result"
    ENDED = "ended"

class PowerUp(Enum):
    HIJACK = "hijack"
    FREEZE = "freeze"
    REWIND = "rewind"
