from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class ParamSfoSnapshot:
    fields: Mapping[str, str]
    raw: bytes
    hash: str
