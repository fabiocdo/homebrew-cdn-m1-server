from enum import Enum


class SorterPlanResult(Enum):
    """Enumeration of sorter dry-run planning results."""
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
