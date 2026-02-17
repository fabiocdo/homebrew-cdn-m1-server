from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PackageAsset:
    path: Path
    size_bytes: int
    mtime_ns: int
