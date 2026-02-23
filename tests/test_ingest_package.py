from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import cast

from homebrew_cdn_m1_server.application.repositories.filesystem_repository import (
    FilesystemRepository,
)
from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import (
    SqliteUnitOfWork,
)
from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.content_id import ContentId
from homebrew_cdn_m1_server.domain.models.results import ProbeResult
from homebrew_cdn_m1_server.domain.protocols.package_probe_protocol import (
    PackageProbeProtocol,
)
from homebrew_cdn_m1_server.domain.protocols.title_metadata_lookup_protocol import (
    TitleMetadataLookupProtocol,
)
from homebrew_cdn_m1_server.domain.workflows.ingest_package import IngestPackage


class _FakeCatalog:
    def __init__(self) -> None:
        self.items: list[CatalogItem] = []

    def upsert(self, item: CatalogItem) -> None:
        self.items.append(item)


class _FakeUow:
    def __init__(self) -> None:
        self.catalog: _FakeCatalog = _FakeCatalog()
        self.committed: bool = False

    def __enter__(self) -> "_FakeUow":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


class _FakeStore:
    def __init__(self, canonical_path: Path) -> None:
        self._canonical_path: Path = canonical_path
        self.errors: list[tuple[Path, str]] = []
        self.raise_on_move: bool = False
        self.raise_on_probe_stat: bool = False

    def move_to_errors(self, pkg_path: Path, reason: str) -> Path:
        self.errors.append((pkg_path, reason))
        return pkg_path

    def move_to_canonical(self, pkg_path: Path, app_type: str, content_id: str) -> Path:
        _ = (pkg_path, app_type, content_id)
        if self.raise_on_move:
            raise RuntimeError("move failed")
        return self._canonical_path

    def stat(self, _pkg_path: Path) -> tuple[int, int]:
        if self.raise_on_probe_stat:
            raise OSError("stat failed")
        stat = self._canonical_path.stat()
        return (int(stat.st_size), int(stat.st_mtime_ns))


class _FakePublisherLookup:
    def __init__(
        self,
        publisher: str | None = None,
        fail: bool = False,
    ) -> None:
        self.publisher: str | None = publisher
        self.fail: bool = fail
        self.lookups: list[str] = []

    def lookup_by_title_id(self, title_id: str) -> str | None:
        self.lookups.append(title_id)
        if self.fail:
            raise RuntimeError("lookup failed")
        return self.publisher


def _probe_result() -> ProbeResult:
    return ProbeResult(
        content_id=ContentId.parse("UP0000-TEST00000_00-TEST000000000000"),
        title_id="CUSA00001",
        title="Game",
        category="GD",
        version="01.00",
        pubtoolinfo="c_date=20250101",
        system_ver="09.00",
        app_type=AppType.GAME,
        release_date="2025-01-01",
        sfo_fields={"TITLE": "Game"},
        sfo_raw=b"sfo",
        sfo_hash="hash",
        icon0_path=None,
        pic0_path=None,
        pic1_path=None,
    )


def test_ingest_package_given_probe_failure_when_called_then_moves_to_errors(
    temp_workspace: Path,
) -> None:
    canonical = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _ = canonical.write_bytes(b"x")
    store = _FakeStore(canonical)
    uow = _FakeUow()

    class _Probe:
        def probe(self, _pkg_path: Path) -> ProbeResult:
            raise RuntimeError("probe failed")

    ingest = IngestPackage(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_probe=cast(PackageProbeProtocol, cast(object, _Probe())),
        package_store=cast(FilesystemRepository, cast(object, store)),
        logger=logging.getLogger("test"),
    )

    incoming = temp_workspace / "incoming.pkg"
    _ = incoming.write_bytes(b"x")
    result = ingest(incoming)

    assert result.item is None
    assert result.created is False
    assert store.errors[-1][1] == "probe_failed"


def test_ingest_package_given_move_failure_when_called_then_moves_to_errors(
    temp_workspace: Path,
) -> None:
    canonical = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _ = canonical.write_bytes(b"x")
    store = _FakeStore(canonical)
    store.raise_on_move = True
    uow = _FakeUow()

    class _Probe:
        def probe(self, _pkg_path: Path) -> ProbeResult:
            return _probe_result()

    ingest = IngestPackage(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_probe=cast(PackageProbeProtocol, cast(object, _Probe())),
        package_store=cast(FilesystemRepository, cast(object, store)),
        logger=logging.getLogger("test"),
    )

    incoming = temp_workspace / "incoming.pkg"
    _ = incoming.write_bytes(b"x")
    result = ingest(incoming)

    assert result.item is None
    assert store.errors[-1][1] == "organizer_failed"


def test_ingest_package_given_fingerprint_failure_when_called_then_moves_to_errors(
    temp_workspace: Path,
) -> None:
    canonical = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _ = canonical.write_bytes(b"x")
    store = _FakeStore(canonical)
    store.raise_on_probe_stat = True
    uow = _FakeUow()

    class _Probe:
        def probe(self, _pkg_path: Path) -> ProbeResult:
            return _probe_result()

    ingest = IngestPackage(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_probe=cast(PackageProbeProtocol, cast(object, _Probe())),
        package_store=cast(FilesystemRepository, cast(object, store)),
        logger=logging.getLogger("test"),
    )

    incoming = temp_workspace / "incoming.pkg"
    _ = incoming.write_bytes(b"x")
    result = ingest(incoming)

    assert result.item is None
    assert store.errors[-1][1] == "fingerprint_failed"


def test_ingest_package_given_valid_pkg_when_called_then_upserts_and_commits(
    temp_workspace: Path,
) -> None:
    canonical = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _ = canonical.write_bytes(b"payload")
    store = _FakeStore(canonical)
    uow = _FakeUow()

    class _Probe:
        def probe(self, _pkg_path: Path) -> ProbeResult:
            return _probe_result()

    metadata_lookup = _FakePublisherLookup("Mojang")
    ingest = IngestPackage(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_probe=cast(PackageProbeProtocol, cast(object, _Probe())),
        package_store=cast(FilesystemRepository, cast(object, store)),
        logger=logging.getLogger("test"),
        metadata_lookup=cast(
            TitleMetadataLookupProtocol, cast(object, metadata_lookup)
        ),
    )

    incoming = temp_workspace / "incoming.pkg"
    _ = incoming.write_bytes(b"x")
    result = ingest(incoming)

    assert result.item is not None
    assert result.created is True
    assert result.item.publisher == "Mojang"
    assert result.item.release_date == "2025-01-01"
    assert len(uow.catalog.items) == 1
    assert uow.committed is True


def test_ingest_package_given_metadata_lookup_failure_when_called_then_keeps_ingestion(
    temp_workspace: Path,
) -> None:
    canonical = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _ = canonical.write_bytes(b"payload")
    store = _FakeStore(canonical)
    uow = _FakeUow()

    class _Probe:
        def probe(self, _pkg_path: Path) -> ProbeResult:
            return _probe_result()

    metadata_lookup = _FakePublisherLookup(fail=True)
    ingest = IngestPackage(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_probe=cast(PackageProbeProtocol, cast(object, _Probe())),
        package_store=cast(FilesystemRepository, cast(object, store)),
        logger=logging.getLogger("test"),
        metadata_lookup=cast(
            TitleMetadataLookupProtocol, cast(object, metadata_lookup)
        ),
    )

    incoming = temp_workspace / "incoming.pkg"
    _ = incoming.write_bytes(b"x")
    result = ingest(incoming)

    assert result.item is not None
    assert result.item.publisher is None
    assert result.created is True
