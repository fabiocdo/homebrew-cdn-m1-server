from enum import Enum


class PlanOutput(Enum):
    ALLOW = "allow"
    REJECT = "reject"
    SKIP = "skip"
