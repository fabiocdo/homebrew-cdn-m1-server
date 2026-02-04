from enum import Enum

from src.models.pkg_app_type import PKGAppType
from src.models.pkg_region import PKGRegion

class PKGDataFields(Enum):
    TITLE: str
    TITLE_ID: str
    CONTENT_ID: str
    CATEGORY: str
    VERSION: str
    RELEASE_DATE: str
    REGION: PKGRegion
    APP_TYPE: PKGAppType
