from enum import Enum


class Stage(Enum):
    LOBBY = "lobby"
    SELECTION = "selection"
    QUESTION = "question"
    FINALE = "finale"
    ENDED = "ended"

class PowerUp(Enum):
    HIJACK = "hijack"
    FREEZE = "freeze"
    REWIND = "rewind"
