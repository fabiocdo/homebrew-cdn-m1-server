from enum import Enum

class PKG:
    class Region(Enum):
        UP = "USA"
        EP = "EUR"
        JP = "JAP"
        HP = "ASIA"
        AP = "ASIA"
        KP = "ASIA"

    class AppType(Enum):
        AC = "dlc"
        GC = "game"
        GD = "game"
        GP = "update"
        SD = "save"

    def __init__(
        self,
        title: str,
        title_id: str,
        content_id: str,
        category: str,
        version: str,
        release_date: str,
        region: Region,
        app_type: AppType,
    ):
        self.title = title
        self.title_id = title_id
        self.content_id = content_id
        self.category = category
        self.version = version
        self.release_date = release_date
        self.region = region
        self.app_type = app_type