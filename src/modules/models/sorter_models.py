from __future__ import annotations

from enum import Enum


class SorterPlanResult(Enum):
    """
    Enumeration of sorter dry-run planning results.

    :param: None
    :return: None
    """
    OK = "ok"
    SKIP = "skip"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
