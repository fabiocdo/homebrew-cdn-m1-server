from __future__ import annotations

from enum import Enum


class PlanOutput(Enum):
    """
    Enumeration of planner output actions.

    :param: None
    :return: None
    """
    ALLOW = "allow"
    REJECT = "reject"
    SKIP = "skip"
