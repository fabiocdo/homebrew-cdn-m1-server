from enum import Enum

class Outputs(Enum):
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    ERROR = "error"

    class Plan(Enum):
        ALLOW = "allow"
        REJECT = "reject"
        SKIP = "skip"