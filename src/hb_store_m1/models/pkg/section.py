from dataclasses import dataclass
from pathlib import Path

from hb_store_m1.models.globals import Globals


@dataclass(frozen=True)
class SectionEntry:
    name: str
    path: Path

    def accepts(self, file: Path) -> bool:
        if not file.is_file():
            return False
        suffix = file.suffix.lower()
        if self.name == "_media":
            return suffix == ".png"
        return suffix == ".pkg"

class Section:
    PKG = SectionEntry("pkg", Globals.PATHS.PKG_DIR_PATH)
    APP = SectionEntry("app", Globals.PATHS.APP_DIR_PATH)
    DLC = SectionEntry("dlc", Globals.PATHS.DLC_DIR_PATH)
    GAME = SectionEntry("game", Globals.PATHS.GAME_DIR_PATH)
    SAVE = SectionEntry("save", Globals.PATHS.SAVE_DIR_PATH)
    UNKNOWN = SectionEntry("unknown", Globals.PATHS.UNKNOWN_DIR_PATH)
    UPDATE = SectionEntry("update", Globals.PATHS.UPDATE_DIR_PATH)
    MEDIA = SectionEntry("_media", Globals.PATHS.MEDIA_DIR_PATH)

    ALL = (PKG, APP, DLC, GAME, SAVE, UNKNOWN, UPDATE, MEDIA)
