from dataclasses import dataclass
from pathlib import Path

from hb_store_m1.models.globals import Globals


@dataclass(frozen=True)
class _Section:
    name: str
    path: Path


class Section:
    PKG = _Section("pkg", Globals.PATHS.PKG_DIR_PATH)
    APP = _Section("app", Globals.PATHS.APP_DIR_PATH)
    DLC = _Section("dlc", Globals.PATHS.DLC_DIR_PATH)
    GAME = _Section("game", Globals.PATHS.GAME_DIR_PATH)
    SAVE = _Section("save", Globals.PATHS.SAVE_DIR_PATH)
    UNKNOWN = _Section("unknown", Globals.PATHS.UNKNOWN_DIR_PATH)
    UPDATE = _Section("update", Globals.PATHS.UPDATE_DIR_PATH)
    MEDIA = _Section("_media", Globals.PATHS.MEDIA_DIR_PATH)

    ALL = (PKG, APP, DLC, GAME, SAVE, UNKNOWN, UPDATE, MEDIA)
