from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.content_id import ContentId


@dataclass(frozen=True, slots=True)
class ProbeResult:
    content_id: ContentId
    title_id: str
    title: str
    category: str
    version: str
    pubtoolinfo: str
    system_ver: str
    app_type: AppType
    release_date: str
    sfo_fields: Mapping[str, str]
    sfo_raw: bytes
    sfo_hash: str
    icon0_path: Path | None
    pic0_path: Path | None
    pic1_path: Path | None


@dataclass(frozen=True, slots=True)
class IngestResult:
    item: CatalogItem | None
    created: bool
    updated: bool


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    added: int
    updated: int
    removed: int
    failed: int
    exported_files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ScanDelta:
    added: tuple[str, ...]
    updated: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)
