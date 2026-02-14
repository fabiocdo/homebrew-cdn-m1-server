from enum import StrEnum


class FPKGI:
    class Column(StrEnum):
        ID = "id"
        NAME = "name"
        VERSION = "version"
        PACKAGE = "package"
        SIZE = "size"
        DESC = "desc"
        ICON = "icon"
        BG_IMAGE = "bg_image"


FPKGI = FPKGI()
