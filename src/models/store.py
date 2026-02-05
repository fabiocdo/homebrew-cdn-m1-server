from enum import Enum

class Store:
    class AppType(Enum):

        GAME = "game"
        UPDATE = "patch"
        DLC = "dlc"
        THEME = "theme"
        APP = "app"
        SAVE = "other"
        OTHER = "Other"