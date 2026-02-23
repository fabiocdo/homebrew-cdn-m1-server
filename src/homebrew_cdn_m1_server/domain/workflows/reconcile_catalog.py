from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from filelock import FileLock, Timeout
from pathlib import Path
from typing import Callable, final

from homebrew_cdn_m1_server.application.repositories.filesystem_repository import (
    FilesystemRepository,
)
from homebrew_cdn_m1_server.application.repositories.json_snapshot_repository import (
    JsonSnapshotRepository,
)
from homebrew_cdn_m1_server.application.repositories.settings_snapshot_repository import (
    SettingsSnapshotRepository,
)
from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import SqliteUnitOfWork
from homebrew_cdn_m1_server.domain.workflows.export_outputs import ExportOutputs
from homebrew_cdn_m1_server.domain.workflows.ingest_package import IngestPackage
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.results import IngestResult, ReconcileResult, ScanDelta


def build_delta(
    previous: dict[str, tuple[int, int]],
    current: dict[str, tuple[int, int]],
) -> ScanDelta:
    previous_keys = set(previous)
    current_keys = set(current)

    added = sorted(current_keys - previous_keys)
    removed = sorted(previous_keys - current_keys)
    updated = sorted(
        key for key in previous_keys & current_keys if previous[key] != current[key]
    )

    return ScanDelta(added=tuple(added), updated=tuple(updated), removed=tuple(removed))


@final
class ReconcileCatalog:
    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        package_store: FilesystemRepository,
        snapshot_store: JsonSnapshotRepository,
        settings_snapshot_store: SettingsSnapshotRepository,
        ingest_package: IngestPackage,
        export_outputs: ExportOutputs,
        lock_path: Path,
        lock_timeout_seconds: float,
        logger: logging.Logger,
        worker_count: int,
        output_targets: tuple[OutputTarget, ...],
    ) -> None:
        self._uow_factory = uow_factory
        self._package_store = package_store
        self._snapshot_store = snapshot_store
        self._settings_snapshot_store = settings_snapshot_store
        self._ingest_package = ingest_package
        self._export_outputs = export_outputs
        self._lock = FileLock(str(lock_path))
        self._lock_timeout_seconds = float(lock_timeout_seconds)
        self._logger = logger
        self._worker_count = max(1, int(worker_count))
        self._output_targets = output_targets

    def _build_snapshot(self) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        for pkg_path in self._package_store.scan_pkg_files():
            try:
                snapshot[str(pkg_path)] = self._package_store.stat(pkg_path)
            except OSError:
                continue
        return snapshot

    @staticmethod
    def _split_results(paths: list[str], results: list[IngestResult]) -> tuple[int, int, int]:
        failures = sum(1 for item in results if item.item is None)
        added = max(0, len(paths) - failures)
        return added, 0, failures

    def _ingest_candidates(self, candidates: list[Path]) -> tuple[int, int, int]:
        if not candidates:
            return 0, 0, 0

        if self._worker_count <= 1 or len(candidates) == 1:
            results = [self._ingest_package(path) for path in candidates]
            return self._split_results([str(p) for p in candidates], results)

        results: list[IngestResult] = []
        with ThreadPoolExecutor(max_workers=self._worker_count) as executor:
            future_by_path = {
                executor.submit(self._ingest_package, path): path for path in candidates
            }
            for future in as_completed(future_by_path):
                path = future_by_path[future]
                try:
                    results.append(future.result())
                except Exception:
                    self._logger.error(
                        "Unexpected ingest worker failure for %s\n%s",
                        path,
                        traceback.format_exc(),
                    )
                    results.append(IngestResult(item=None, created=False, updated=False))
        return self._split_results([str(p) for p in candidates], results)

    def __call__(self) -> ReconcileResult:
        try:
            _ = self._lock.acquire(timeout=self._lock_timeout_seconds)
        except Timeout:
            self._logger.warning("Reconcile skipped: another cycle is still running")
            return ReconcileResult(0, 0, 0, 0, tuple())

        try:
            previous = dict(self._snapshot_store.load())
            current = self._build_snapshot()
            delta = build_delta(previous, current)
            previous_settings_hash = self._settings_snapshot_store.load()
            current_settings_hash = self._settings_snapshot_store.current_hash()
            settings_changed = previous_settings_hash != current_settings_hash

            if settings_changed:
                candidates = [Path(path) for path in sorted(current)]
            else:
                candidates = [Path(path) for path in (*delta.added, *delta.updated)]
            added, updated, failed = self._ingest_candidates(candidates)

            final_snapshot = self._build_snapshot()
            existing_paths = set(final_snapshot)

            with self._uow_factory() as uow:
                removed = uow.catalog.delete_by_pkg_paths_not_in(existing_paths)
                uow.commit()

            exported_files = self._export_outputs(self._output_targets)
            self._snapshot_store.save(final_snapshot)
            self._settings_snapshot_store.save(current_settings_hash)

            has_changes = bool(added or updated or removed or failed)
            log_fn = self._logger.info if has_changes else self._logger.debug
            log_fn(
                "Reconcile completed: added: %d, updated: %d, removed: %d, failed: %d",
                added,
                updated,
                removed,
                failed,
            )
            return ReconcileResult(
                added=added,
                updated=updated,
                removed=removed,
                failed=failed,
                exported_files=exported_files,
            )
        finally:
            self._lock.release()
