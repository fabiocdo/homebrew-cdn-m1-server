from __future__ import annotations

from typing import Protocol


class LockPort(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> None: ...
