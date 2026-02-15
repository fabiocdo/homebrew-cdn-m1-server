from enum import StrEnum


class FPKGI:
    class Root(StrEnum):
        DATA = "DATA"

    class Column(StrEnum):
        TITLE_ID = "title_id"
        REGION = "region"
        NAME = "name"
        VERSION = "version"
        RELEASE = "release"
        SIZE = "size"
        MIN_FW = "min_fw"
        COVER_URL = "cover_url"

    class LegacyColumn(StrEnum):
        ID = "id"
        NAME = "name"
        VERSION = "version"
        PACKAGE = "package"
        SIZE = "size"
        DESC = "desc"
        ICON = "icon"
        BG_IMAGE = "bg_image"
