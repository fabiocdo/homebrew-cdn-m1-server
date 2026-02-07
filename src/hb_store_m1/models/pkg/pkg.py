from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from hb_store_m1.models.pkg.metadata import PKGEntry, ParamSFO


class Region(StrEnum):
    UP = "USA"
    EP = "EUR"
    JP = "JAP"
    HP = "ASIA"
    AP = "ASIA"
    KP = "ASIA"
    UNKNOWN = "UNKNOWN"


class AppType(StrEnum):
    AC = "dlc"
    GC = "game"
    GD = "game"
    GP = "update"
    SD = "save"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class PKG:
    title: str = ""
    title_id: str = ""
    content_id: str = ""
    category: str = ""
    version: str = ""
    release_date: str = ""
    icon0_png: str = ""
    pic0_png: str = ""
    pic1_png: str = ""
    region: Region | None = None
    app_type: AppType | None = None
    entries: list[PKGEntry] = field(default_factory=list)
    param_sfo: ParamSFO = field(default_factory=ParamSFO)

    def __post_init__(self) -> None:
        # app_type
        cat = (self.category or "").strip().upper()
        self.app_type = AppType.__members__.get(cat, AppType.UNKNOWN)

        # region
        if len(self.content_id or "") >= 2:
            prefix = self.content_id[:2].upper()
            self.region = Region.__members__.get(prefix, Region.UNKNOWN)
        else:
            self.region = Region.UNKNOWN
