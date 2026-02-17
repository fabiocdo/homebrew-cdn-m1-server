from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable, final

from homebrew_cdn_m1_server.application.repositories.filesystem_repository import (
    FilesystemRepository,
)
from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import SqliteUnitOfWork
from homebrew_cdn_m1_server.domain.protocols.package_probe_protocol import PackageProbeProtocol
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.param_sfo_snapshot import ParamSfoSnapshot
from homebrew_cdn_m1_server.domain.models.results import IngestResult


def fingerprint_pkg(path: Path, size: int, mtime_ns: int) -> str:
    digest = hashlib.blake2b(digest_size=16)
    digest.update(f"{size}:{mtime_ns}".encode("utf-8"))

    with path.open("rb") as stream:
        head = stream.read(64 * 1024)
        digest.update(head)

        if size > 64 * 1024:
            tail_size = min(size, 64 * 1024)
            _ = stream.seek(max(0, size - tail_size))
            digest.update(stream.read(tail_size))

    return digest.hexdigest()


@final
class IngestPackage:
    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        package_probe: PackageProbeProtocol,
        package_store: FilesystemRepository,
        logger: logging.Logger,
    ) -> None:
        self._uow_factory = uow_factory
        self._package_probe = package_probe
        self._package_store = package_store
        self._logger = logger

    def __call__(self, pkg_path: Path) -> IngestResult:
        try:
            probe = self._package_probe.probe(pkg_path)
        except Exception as exc:
            self._logger.error("Failed to probe %s: %s", pkg_path.name, exc)
            _ = self._package_store.move_to_errors(pkg_path, "probe_failed")
            return IngestResult(item=None, created=False, updated=False)

        try:
            canonical_path = self._package_store.move_to_canonical(
                pkg_path,
                probe.app_type.value,
                probe.content_id.value,
            )
        except Exception as exc:
            self._logger.error("Failed to move %s to canonical path: %s", pkg_path.name, exc)
            _ = self._package_store.move_to_errors(pkg_path, "organizer_failed")
            return IngestResult(item=None, created=False, updated=False)

        try:
            size, mtime_ns = self._package_store.stat(canonical_path)
            pkg_fp = fingerprint_pkg(canonical_path, size, mtime_ns)
        except Exception as exc:
            self._logger.error("Failed to fingerprint %s: %s", canonical_path.name, exc)
            _ = self._package_store.move_to_errors(canonical_path, "fingerprint_failed")
            return IngestResult(item=None, created=False, updated=False)

        item = CatalogItem(
            content_id=probe.content_id,
            title_id=probe.title_id,
            title=probe.title,
            app_type=probe.app_type,
            category=probe.category,
            version=probe.version,
            pubtoolinfo=probe.pubtoolinfo,
            system_ver=probe.system_ver,
            release_date=probe.release_date,
            pkg_path=canonical_path,
            pkg_size=size,
            pkg_mtime_ns=mtime_ns,
            pkg_fingerprint=pkg_fp,
            icon0_path=probe.icon0_path,
            pic0_path=probe.pic0_path,
            pic1_path=probe.pic1_path,
            sfo=ParamSfoSnapshot(
                fields=dict(probe.sfo_fields),
                raw=probe.sfo_raw,
                hash=probe.sfo_hash,
            ),
        )

        with self._uow_factory() as uow:
            uow.catalog.upsert(item)
            uow.commit()

        self._logger.info(
            "Catalog upserted: content_id: %s, app_type: %s, version: %s",
            item.content_id.value,
            item.app_type.value,
            item.version,
        )
        return IngestResult(item=item, created=True, updated=False)
