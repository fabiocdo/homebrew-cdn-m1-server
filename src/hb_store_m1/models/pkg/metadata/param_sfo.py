from dataclasses import dataclass
from enum import StrEnum


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


@dataclass(slots=True)
class ParamSFO:
    key: ParamSFOKey
    value: str

    def __init__(self, key: ParamSFOKey, value: str):
        self.key = key
        self.value = value
