from __future__ import annotations

from enum import StrEnum


class AppType(StrEnum):
    APP = "app"
    GAME = "game"
    DLC = "dlc"
    UPDATE = "update"
    SAVE = "save"
    UNKNOWN = "unknown"

    @classmethod
    def from_category(cls, category: str) -> "AppType":
        value = str(category or "").strip().upper()
        mapping = {
            "AC": cls.DLC,
            "GC": cls.GAME,
            "GD": cls.GAME,
            "GP": cls.UPDATE,
            "SD": cls.SAVE,
        }
        return mapping.get(value, cls.UNKNOWN)

    @property
    def store_db_label(self) -> str:
        mapping = {
            AppType.APP: "App",
            AppType.GAME: "Game",
            AppType.DLC: "DLC",
            AppType.UPDATE: "Patch",
            AppType.SAVE: "Save",
            AppType.UNKNOWN: "Unknown",
        }
        return mapping[self]
