from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Callable, cast, override

import pytest
from filelock import Timeout

from homebrew_cdn_m1_server.application.repositories.filesystem_repository import (
    FilesystemRepository,
)
from homebrew_cdn_m1_server.application.repositories.json_snapshot_repository import (
    JsonSnapshotRepository,
)
from homebrew_cdn_m1_server.application.repositories.settings_snapshot_repository import (
    SettingsSnapshotRepository,
)
from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import (
    SqliteUnitOfWork,
)
from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.content_id import ContentId
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.param_sfo_snapshot import ParamSfoSnapshot
from homebrew_cdn_m1_server.domain.models.results import IngestResult
from homebrew_cdn_m1_server.domain.workflows import reconcile_catalog as module
from homebrew_cdn_m1_server.domain.workflows.export_outputs import ExportOutputs
from homebrew_cdn_m1_server.domain.workflows.ingest_package import IngestPackage
from homebrew_cdn_m1_server.domain.workflows.reconcile_catalog import (
    ReconcileCatalog,
    build_delta,
)


def _catalog_item(path: Path) -> CatalogItem:
    return CatalogItem(
        content_id=ContentId.parse("UP0000-TEST00000_00-TEST000000000000"),
        title_id="CUSA00001",
        title="Game",
        app_type=AppType.GAME,
        category="GD",
        version="01.00",
        pubtoolinfo="c_date=20250101",
        system_ver="09.00",
        release_date="2025-01-01",
        pkg_path=path,
        pkg_size=10,
        pkg_mtime_ns=20,
        pkg_fingerprint="fp",
        icon0_path=None,
        pic0_path=None,
        pic1_path=None,
        sfo=ParamSfoSnapshot(fields={"TITLE": "Game"}, raw=b"sfo", hash="hash"),
    )


class _FakePackageStore:
    def __init__(self, snapshot: dict[Path, tuple[int, int]], failing: set[Path] | None = None) -> None:
        self._snapshot: dict[Path, tuple[int, int]] = snapshot
        self._failing: set[Path] = failing or set()

    def scan_pkg_files(self) -> list[Path]:
        return sorted(self._snapshot.keys())

    def stat(self, pkg_path: Path) -> tuple[int, int]:
        if pkg_path in self._failing:
            raise OSError("stat failed")
        return self._snapshot[pkg_path]


class _FakeSnapshotRepository:
    def __init__(self, previous: dict[str, tuple[int, int]]) -> None:
        self._previous: dict[str, tuple[int, int]] = previous
        self.saved: dict[str, tuple[int, int]] | None = None

    def load(self) -> dict[str, tuple[int, int]]:
        return dict(self._previous)

    def save(self, snapshot: dict[str, tuple[int, int]]) -> None:
        self.saved = dict(snapshot)


class _FakeSettingsSnapshotRepository:
    def __init__(self, previous_hash: str, current_hash: str) -> None:
        self._previous_hash = previous_hash
        self._current_hash = current_hash
        self.saved_hash: str | None = None

    def load(self) -> str:
        return self._previous_hash

    def current_hash(self) -> str:
        return self._current_hash

    def save(self, hash_value: str) -> None:
        self.saved_hash = str(hash_value)


class _FakeCatalog:
    def __init__(self, removed: int) -> None:
        self._removed: int = removed
        self.received_paths: set[str] | None = None

    def delete_by_pkg_paths_not_in(self, existing_pkg_paths: set[str]) -> int:
        self.received_paths = set(existing_pkg_paths)
        return self._removed


class _FakeUow:
    def __init__(self, removed: int) -> None:
        self.catalog: _FakeCatalog = _FakeCatalog(removed)
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


class _FakeExportOutputs:
    def __init__(self, exported: tuple[Path, ...]) -> None:
        self._exported: tuple[Path, ...] = exported
        self.calls: list[tuple[OutputTarget, ...]] = []

    def __call__(self, targets: tuple[OutputTarget, ...]) -> tuple[Path, ...]:
        self.calls.append(targets)
        return self._exported


class _FakeIngest:
    def __init__(self, failing_paths: set[Path] | None = None) -> None:
        self.failing_paths: set[Path] = failing_paths or set()
        self.calls: list[Path] = []

    def __call__(self, path: Path) -> IngestResult:
        self.calls.append(path)
        if path in self.failing_paths:
            raise RuntimeError("worker failure")
        return IngestResult(item=_catalog_item(path), created=True, updated=False)


class _NoopLock:
    def __init__(self, _path: str) -> None:
        self.acquired: bool = False
        self.released: bool = False

    def acquire(
        self,
        timeout: float | None = None,
        poll_interval: float | None = None,
        *,
        poll_intervall: float | None = None,
        blocking: bool | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> object:
        _ = (timeout, poll_interval, poll_intervall, blocking, cancel_check)
        self.acquired = True
        return object()

    def release(self, force: bool = False) -> None:
        _ = force
        self.released = True


class _TimeoutLock(_NoopLock):
    @override
    def acquire(
        self,
        timeout: float | None = None,
        poll_interval: float | None = None,
        *,
        poll_intervall: float | None = None,
        blocking: bool | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> object:
        _ = (timeout, poll_interval, poll_intervall, blocking, cancel_check)
        raise Timeout("busy")


def _build_reconcile(
    temp_workspace: Path,
    package_snapshot: dict[Path, tuple[int, int]],
    previous_snapshot: dict[str, tuple[int, int]],
    ingest: _FakeIngest,
    *,
    removed: int = 0,
    worker_count: int = 1,
    failing_stats: set[Path] | None = None,
) -> tuple[
    ReconcileCatalog,
    _FakeSnapshotRepository,
    _FakeSettingsSnapshotRepository,
    _FakeExportOutputs,
    _FakeUow,
]:
    package_store = _FakePackageStore(package_snapshot, failing=failing_stats)
    snapshot_store = _FakeSnapshotRepository(previous_snapshot)
    settings_snapshot_store = _FakeSettingsSnapshotRepository(
        previous_hash="hash-a",
        current_hash="hash-a",
    )
    exported = (
        temp_workspace / "data" / "share" / "hb-store" / "store.db",
        temp_workspace / "data" / "share" / "fpkgi" / "GAMES.json",
    )
    export_outputs = _FakeExportOutputs(exported)
    uow = _FakeUow(removed=removed)

    reconcile = ReconcileCatalog(
        uow_factory=lambda: cast(SqliteUnitOfWork, cast(object, uow)),
        package_store=cast(FilesystemRepository, cast(object, package_store)),
        snapshot_store=cast(JsonSnapshotRepository, cast(object, snapshot_store)),
        settings_snapshot_store=cast(
            SettingsSnapshotRepository, cast(object, settings_snapshot_store)
        ),
        ingest_package=cast(IngestPackage, cast(object, ingest)),
        export_outputs=cast(ExportOutputs, cast(object, export_outputs)),
        lock_path=temp_workspace / "data" / "internal" / "snapshot" / "reconcile.lock",
        lock_timeout_seconds=0.0,
        logger=logging.getLogger("test"),
        worker_count=worker_count,
        output_targets=(OutputTarget.HB_STORE, OutputTarget.FPKGI),
    )
    return reconcile, snapshot_store, settings_snapshot_store, export_outputs, uow


def test_build_delta_given_previous_and_current_when_called_then_returns_expected_sets() -> None:
    previous = {"a.pkg": (1, 10), "b.pkg": (2, 20)}
    current = {"b.pkg": (2, 21), "c.pkg": (3, 30)}

    delta = build_delta(previous, current)

    assert delta.added == ("c.pkg",)
    assert delta.updated == ("b.pkg",)
    assert delta.removed == ("a.pkg",)
    assert delta.has_changes is True


def test_reconcile_catalog_given_lock_timeout_when_called_then_skips(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "FileLock", _TimeoutLock)
    reconcile, _, _, export_outputs, _ = _build_reconcile(
        temp_workspace,
        package_snapshot={},
        previous_snapshot={},
        ingest=_FakeIngest(),
    )

    result = reconcile()

    assert result.added == 0
    assert result.updated == 0
    assert result.removed == 0
    assert result.failed == 0
    assert result.exported_files == tuple()
    assert export_outputs.calls == []


def test_reconcile_catalog_given_stat_failure_when_called_then_ignores_bad_entry(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "FileLock", _NoopLock)
    ok = temp_workspace / "ok.pkg"
    bad = temp_workspace / "bad.pkg"
    _ = ok.write_bytes(b"ok")
    _ = bad.write_bytes(b"bad")

    reconcile, snapshot_store, settings_snapshot_store, _, _ = _build_reconcile(
        temp_workspace,
        package_snapshot={ok: (1, 2), bad: (3, 4)},
        previous_snapshot={},
        ingest=_FakeIngest(),
        failing_stats={bad},
    )

    result = reconcile()

    assert result.added == 1
    assert result.failed == 0
    assert snapshot_store.saved == {str(ok): (1, 2)}
    assert settings_snapshot_store.saved_hash == "hash-a"


def test_reconcile_catalog_given_worker_failure_when_called_then_counts_failed(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "FileLock", _NoopLock)
    p1 = temp_workspace / "a.pkg"
    p2 = temp_workspace / "b.pkg"
    _ = p1.write_bytes(b"a")
    _ = p2.write_bytes(b"b")

    ingest = _FakeIngest(failing_paths={p2})
    reconcile, _, _, export_outputs, _ = _build_reconcile(
        temp_workspace,
        package_snapshot={p1: (1, 10), p2: (2, 20)},
        previous_snapshot={},
        ingest=ingest,
        worker_count=2,
    )

    result = reconcile()

    assert result.added == 1
    assert result.updated == 0
    assert result.failed == 1
    assert len(export_outputs.calls) == 1


def test_reconcile_catalog_given_changes_when_called_then_reconciles_and_exports(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "FileLock", _NoopLock)
    pkg = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    pkg.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg.write_bytes(b"x")

    reconcile, _, _, export_outputs, uow = _build_reconcile(
        temp_workspace,
        package_snapshot={pkg: (1, 100)},
        previous_snapshot={"old.pkg": (1, 1)},
        ingest=_FakeIngest(),
        removed=2,
    )

    result = reconcile()

    assert result.added == 1
    assert result.updated == 0
    assert result.removed == 2
    assert result.failed == 0
    assert len(result.exported_files) == 2
    assert len(export_outputs.calls) == 1
    assert uow.committed is True


def test_reconcile_catalog_given_settings_hash_changed_when_called_then_reprocesses_all_pkgs(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "FileLock", _NoopLock)
    p1 = temp_workspace / "data" / "share" / "pkg" / "game" / "A.pkg"
    p2 = temp_workspace / "data" / "share" / "pkg" / "game" / "B.pkg"
    p1.parent.mkdir(parents=True, exist_ok=True)
    _ = p1.write_bytes(b"a")
    _ = p2.write_bytes(b"b")

    previous = {
        str(p1): (1, 10),
        str(p2): (2, 20),
    }
    ingest = _FakeIngest()
    reconcile, _, settings_snapshot_store, _, _ = _build_reconcile(
        temp_workspace,
        package_snapshot={p1: (1, 10), p2: (2, 20)},
        previous_snapshot=previous,
        ingest=ingest,
    )
    settings_snapshot_store._previous_hash = "hash-old"
    settings_snapshot_store._current_hash = "hash-new"

    result = reconcile()

    assert result.added == 2
    assert result.failed == 0
    assert set(ingest.calls) == {p1, p2}
