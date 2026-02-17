from __future__ import annotations

from collections.abc import Iterable
import logging
from pathlib import Path
from typing import Callable, final

from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import SqliteUnitOfWork
from homebrew_cdn_m1_server.domain.protocols.output_exporter_protocol import OutputExporterProtocol
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget


@final
class ExportOutputs:
    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        exporters: Iterable[OutputExporterProtocol],
        logger: logging.Logger,
    ) -> None:
        self._uow_factory = uow_factory
        self._exporters = {exporter.target: exporter for exporter in exporters}
        self._logger = logger

    def __call__(self, targets: tuple[OutputTarget, ...]) -> tuple[Path, ...]:
        with self._uow_factory() as uow:
            items = uow.catalog.list_items()

        enabled_targets = set(targets)
        exported: list[Path] = []
        for target in targets:
            exporter = self._exporters.get(target)
            if not exporter:
                self._logger.warning("Output target not registered: %s", target.value)
                continue
            files = exporter.export(items)
            exported.extend(files)
            self._logger.debug(
                "%s Export completed: %d updated",
                target.value.upper(),
                len(items),
            )

        for target, exporter in self._exporters.items():
            if target in enabled_targets:
                continue
            removed_files = exporter.cleanup()
            if not removed_files:
                continue
            self._logger.info(
                "Disabled output cleaned: target: %s, files: %d",
                target.value,
                len(removed_files),
            )

        return tuple(exported)
