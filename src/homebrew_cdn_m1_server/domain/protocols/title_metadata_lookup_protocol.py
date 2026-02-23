from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TitleMetadataLookupProtocol(Protocol):
    def lookup_by_title_id(self, title_id: str) -> str | None:
        ...
