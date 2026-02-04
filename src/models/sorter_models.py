from enum import Enum

class SorterPlanResult(Enum):
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
