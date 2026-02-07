from dataclasses import dataclass
from enum import StrEnum


class ParamSFOKey(StrEnum):
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
    data: dict[ParamSFOKey, str]

    # def __init__(self, data: dict[ParamSFOKey, str]):
    #     self.data = data
