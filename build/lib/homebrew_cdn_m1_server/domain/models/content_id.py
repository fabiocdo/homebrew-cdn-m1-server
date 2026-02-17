from __future__ import annotations

import re
from dataclasses import dataclass
from typing import override

_CONTENT_ID_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$")


@dataclass(frozen=True, slots=True)
class ContentId:
    value: str

    @classmethod
    def parse(cls, raw: str) -> "ContentId":
        normalized = str(raw or "").strip().upper()
        if not _CONTENT_ID_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid content_id: {raw!r}")
        return cls(normalized)

    @override
    def __str__(self) -> str:
        return self.value
