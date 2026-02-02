from enum import Enum


class FormatterPlanResult(Enum):
    """Enumeration of formatter dry-run planning results."""
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
