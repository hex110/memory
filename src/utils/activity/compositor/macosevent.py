from enum import Enum

class EventType(Enum):
    WINDOW_INFO = "WINDOW_INFO"
    APPLICATION = "APPLICATION"
    KEYBOARD = "KEYBOARD"
    MOUSE = "MOUSE"
    SCROLL = "SCROLL"
    MODIFIER = "MODIFIER"
    CHARACTER = "CHARACTER"
    SPECIAL_KEY = "SPECIAL_KEY"