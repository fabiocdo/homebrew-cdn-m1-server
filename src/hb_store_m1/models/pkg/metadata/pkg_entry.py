from dataclasses import dataclass
from enum import StrEnum


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
