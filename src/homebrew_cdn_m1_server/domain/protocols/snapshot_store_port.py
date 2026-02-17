from __future__ import annotations

from typing import Mapping, Protocol


class SnapshotStorePort(Protocol):
    def load(self) -> Mapping[str, tuple[int, int]]: ...

    def save(self, snapshot: Mapping[str, tuple[int, int]]) -> None: ...
