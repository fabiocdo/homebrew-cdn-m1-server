from dataclasses import dataclass
from enum import Enum, auto


class Status(Enum):
    OK = auto()
    SKIP = auto()
    CONFLICT = auto()
    NOT_FOUND = auto()
    INVALID = auto()
    ERROR = auto()
    WARN = auto()
    ALLOW = auto()
    REJECT = auto()


@dataclass(slots=True)
class Output[T]:
    status: Status
    content: T | None = None
