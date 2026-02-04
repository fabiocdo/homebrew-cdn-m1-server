from enum import Enum

class StoreAppType(Enum):
    game = "Game"
    update = "Patch"
    dlc = "DLC"
    theme = "Theme"
    app = "App"
    save = "Other"
    unknown = "Other"
    other = "Other"
