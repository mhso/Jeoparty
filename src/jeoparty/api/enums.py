from enum import Enum

class Environment(Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TESTING = "testing"

class StageType(Enum):
    LOBBY = "lobby"
    SELECTION = "selection"
    QUESTION = "question"
    FINALE_WAGER = "finale_wager"
    FINALE_QUESTION = "finale_question"
    FINALE_RESULT = "finale_result"
    ENDED = "ended"

class PowerUpType(Enum):
    HIJACK = "hijack"
    FREEZE = "freeze"
    REWIND = "rewind"

class Language(Enum):
    DANISH = "danish"
    ENGLISH = "english"
