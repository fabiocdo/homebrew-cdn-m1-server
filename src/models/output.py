from enum import Enum

class Output(Enum):
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    ERROR = "error"
    ALLOW = "allow"
    REJECT = "reject"