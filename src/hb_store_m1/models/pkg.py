from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto, Enum


class EntryKey(StrEnum):
    PARAM_SFO = auto()
    ICON0_PNG = auto()
    PIC0_PNG = auto()
    PIC1_PNG = auto()


class ParamSFOKey(StrEnum):
    APP_VER = auto()
    CATEGORY = auto()
    CONTENT_ID = auto()
    PUBTOOLINFO = auto()
    SYSTEM_VER = auto()
    TITLE = auto()
    TITLE_ID = auto()
    VERSION = auto()


class Severity(StrEnum):
    CRITICAL = auto()
    NON_CRITICAL = auto()


class ValidationFields(Enum):
    # Critical
    CONTENT_DIGEST = ["Content Digest", Severity.CRITICAL]
    BODY_DIGEST = ["Body Digest", Severity.CRITICAL]
    PFS_IMAGE_DIGEST = ["PFS Image Digest", Severity.CRITICAL]
    PFS_SIGNED_DIGEST = ["PFS Signed Digest", Severity.CRITICAL]
    DIGEST_TABLE_HASH = ["Digest Table Hash", Severity.CRITICAL]
    SC_ENTRIES_HASH_1 = ["SC Entries Hash 1", Severity.CRITICAL]
    SC_ENTRIES_HASH_2 = ["SC Entries Hash 2", Severity.CRITICAL]
    PKG_HEADER_DIGEST = ["PKG Header Digest", Severity.CRITICAL]
    PKG_HEADER_SIGNATURE = ["PKG Header Signature", Severity.CRITICAL]
    ICON0_PNG = ["ICON0_PNG digest", Severity.CRITICAL]
    # Non-Critical
    MAJOR_PARAM_DIGEST = ["Major Param Digest", Severity.NON_CRITICAL]
    PARAM_DIGEST = ["Param Digest", Severity.NON_CRITICAL]
    PIC0_PNG_DIGEST = ["PIC0_PNG digest", Severity.NON_CRITICAL]
    PIC1_PNG_DIGEST = ["PIC1_PNG digest", Severity.NON_CRITICAL]


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
    region: Region | None = None
    app_type: AppType | None = None
    Entries: dict[EntryKey, int] = field(default_factory=dict)
    ParamSFO: dict[ParamSFOKey, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:

        # app_type value
        cat = self.category.strip().upper()
        self.app_type = AppType.__members__.get(cat, AppType.UNKNOWN)

        # region value
        if len(self.content_id) >= 2:
            prefix = self.content_id[:2].upper()
            self.region = Region.__members__.get(prefix, AppType.UNKNOWN)
