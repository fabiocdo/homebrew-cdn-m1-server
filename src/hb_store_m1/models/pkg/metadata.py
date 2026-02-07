from dataclasses import dataclass
from enum import StrEnum


class EntryKey(StrEnum):
    PARAM_SFO = "PARAM_SFO"
    ICON0_PNG = "ICON0_PNG"
    PIC0_PNG = "PIC0_PNG"
    PIC1_PNG = "PIC1_PNG"


@dataclass(slots=True)
class ParamSFO:
    app_ver: str
    category: str
    content_id: str
    pubtoolinfo: str
    system_ver: str
    title: str
    title_id: str
    version: str


@dataclass(slots=True)
class PKGEntry:
    key: EntryKey
    index: str

    def __init__(self, key: EntryKey, index: str):
        self.key = key
        self.index = index
