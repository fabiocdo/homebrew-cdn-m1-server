from enum import Enum, auto, StrEnum


class Severity(StrEnum):
    CRITICAL = auto()
    NON_CRITICAL = auto()


class ValidationFields(Enum):
    # Critical
    PKG_HEADER_DIGEST = ["PKG Header Digest", Severity.CRITICAL]
    DIGEST_TABLE_HASH = ["Digest Table Hash", Severity.CRITICAL]
    SC_ENTRIES_HASH_1 = ["SC Entries Hash 1", Severity.CRITICAL]
    SC_ENTRIES_HASH_2 = ["SC Entries Hash 2", Severity.CRITICAL]
    ICON0_PNG = ["ICON0_PNG digest", Severity.CRITICAL]
    # Non-Critical
    PKG_HEADER_SIGNATURE = ["PKG Header Signature", Severity.NON_CRITICAL]
    MAJOR_PARAM_DIGEST = ["Major Param Digest", Severity.NON_CRITICAL]
    PARAM_DIGEST = ["Param Digest", Severity.NON_CRITICAL]
    PFS_IMAGE_DIGEST = ["PFS Image Digest", Severity.NON_CRITICAL]
    PFS_SIGNED_DIGEST = ["PFS Signed Digest", Severity.NON_CRITICAL]
    CONTENT_DIGEST = ["Content Digest", Severity.NON_CRITICAL]
    BODY_DIGEST = ["Body Digest", Severity.NON_CRITICAL]
    PIC0_PNG_DIGEST = ["PIC0_PNG digest", Severity.NON_CRITICAL]
    PIC1_PNG_DIGEST = ["PIC1_PNG digest", Severity.NON_CRITICAL]
