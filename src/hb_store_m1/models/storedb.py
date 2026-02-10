from dataclasses import dataclass
from enum import StrEnum


@dataclass(slots=True)
class StoreDB:
    class Column(StrEnum):
        ID = "id"
        NAME = "name"
        CONTENT_ID = "content_id"
        DESC = "desc"
        IMAGE = "image"
        PACKAGE = "package"
        VERSION = "version"
        PIC_PATH = "picpath"
        DESC_1 = "desc_1"
        DESC_2 = "desc_2"
        REVIEW_STARS = "ReviewStars"
        SIZE = "Size"
        AUTHOR = "Author"
        APP_TYPE = "apptype"
        PV = "pv"
        MAIN_ICON_PATH = "main_icon_path"
        MAIN_MENU_PIC = "main_menu_pic"
        RELEASEDDATE = "releaseddate"
        NUMBER_OF_DOWNLOADS = "number_of_downloads"
        GITHUB = "github"
        VIDEO = "video"
        TWITTER = "twitter"
        MD5 = "md5"

    row: dict[Column, str | float | int | None]
