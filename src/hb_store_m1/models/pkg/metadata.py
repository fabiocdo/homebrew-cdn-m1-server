from dataclasses import dataclass
from enum import StrEnum


## PKG ENTRY
class PKGEntryKey(StrEnum):
    PARAM_SFO = "PARAM_SFO"
    ICON0_PNG = "ICON0_PNG"
    PIC0_PNG = "PIC0_PNG"
    PIC1_PNG = "PIC1_PNG"


@dataclass(slots=True)
class PKGEntry:
    key: PKGEntryKey
    index: str

    def __init__(self, key: PKGEntryKey, index: str):
        self.key = key
        self.index = index


## PARAM_SFO
class ParamSFOKey(StrEnum):
    APP_TYPE = "APP_TYPE"
    APP_VER = "APP_VER"
    CATEGORY = "CATEGORY"
    CONTENT_ID = "CONTENT_ID"
    PUBTOOLINFO = "PUBTOOLINFO"
    SYSTEM_VER = "SYSTEM_VER"
    TITLE = "TITLE"
    TITLE_ID = "TITLE_ID"
    VERSION = "VERSION"


class ParamSFOValue:
    type: str
    size: int
    max_size: int
    value: str


@dataclass(slots=True)
class ParamSFO:
    data: dict[ParamSFOKey, ParamSFOValue]

    def __init__(self, data: dict[ParamSFOKey, ParamSFOValue]):
        self.data = data
