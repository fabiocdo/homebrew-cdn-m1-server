from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum, Enum
from pathlib import Path


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


# TODO CHECK
class Media(Enum):
    ICON0_PNG = Path("icon0.png")
    PIC0_PNG = Path("icon0.png")
    PIC1_PNG = Path("icon0.png")


@dataclass(slots=True)
class PKG:
    title: str = ""
    title_id: str = ""
    content_id: str = ""
    category: str = ""
    version: str = ""
    pubtoolinfo: str = ""
    release_date: str = ""
    region: Region | None = None
    app_type: AppType | None = None
    icon0_png_path: Path = None
    pic0_png_path: Path = None
    pic1_png_path: Path = None
    pkg_path: Path = None
    pkg_url: str | None = None
    icon_url: str | None = None
    pic0_url: str | None = None
    pic1_url: str | None = None
    size: int = 0
    row_md5: str | None = None

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

        # release_date
        if not (self.release_date or "").strip() and self.pubtoolinfo:
            match = re.search(r"\bc_date=(\d{8})\b", self.pubtoolinfo)
            if match:
                ymd = match.group(1)
                self.release_date = f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
