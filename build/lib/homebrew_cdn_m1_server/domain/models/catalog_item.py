from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from homebrew_cdn_m1_server.domain.models.param_sfo_snapshot import ParamSfoSnapshot
from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.content_id import ContentId


@dataclass(frozen=True, slots=True)
class CatalogItem:
    _BYTES_PER_MB: ClassVar[int] = 1024 * 1024
    _BYTES_PER_GB: ClassVar[int] = 1024 * 1024 * 1024

    content_id: ContentId
    title_id: str
    title: str
    app_type: AppType
    category: str
    version: str
    pubtoolinfo: str
    system_ver: str
    release_date: str
    pkg_path: Path
    pkg_size: int
    pkg_mtime_ns: int
    pkg_fingerprint: str
    icon0_path: Path | None
    pic0_path: Path | None
    pic1_path: Path | None
    sfo: ParamSfoSnapshot
    downloads: int = 0

    def to_mb(self) -> float:
        return float(self.pkg_size) / self._BYTES_PER_MB

    def to_gb(self) -> float:
        return float(self.pkg_size) / self._BYTES_PER_GB
