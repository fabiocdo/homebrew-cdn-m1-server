from __future__ import annotations

from pathlib import Path
from typing import Sequence

from homebrew_cdn_m1_server.application.use_cases.export_outputs import ExportOutputs
from homebrew_cdn_m1_server.config.settings_models import OutputTarget
from homebrew_cdn_m1_server.domain.entities.catalog_item import CatalogItem


class _FakeCatalogRepository:
    def __init__(self, items: Sequence[CatalogItem]) -> None:
        self._items = list(items)

    def init_schema(self, schema_sql: str) -> None:
        _ = schema_sql

    def upsert(self, item: CatalogItem) -> None:
        _ = item

    def list_items(self) -> list[CatalogItem]:
        return list(self._items)

    def delete_by_pkg_paths_not_in(self, existing_pkg_paths: set[str]) -> int:
        _ = existing_pkg_paths
        return 0


class _FakeUnitOfWork:
    def __init__(self, items: Sequence[CatalogItem]) -> None:
        self.catalog = _FakeCatalogRepository(items)

    def __enter__(self) -> "_FakeUnitOfWork":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def debug(self, msg: object, *args: object) -> None:
        _ = (msg, args)

    def info(self, msg: object, *args: object) -> None:
        text = str(msg) % args if args else str(msg)
        self.infos.append(text)

    def warning(self, msg: object, *args: object) -> None:
        text = str(msg) % args if args else str(msg)
        self.warnings.append(text)

    def error(self, msg: object, *args: object) -> None:
        text = str(msg) % args if args else str(msg)
        self.errors.append(text)

    def exception(self, msg: object, *args: object) -> None:
        self.error(msg, *args)


class _FakeExporter:
    def __init__(
        self,
        target: OutputTarget,
        export_result: Sequence[Path],
        cleanup_result: Sequence[Path],
    ) -> None:
        self.target = target
        self._export_result = list(export_result)
        self._cleanup_result = list(cleanup_result)
        self.export_calls = 0
        self.cleanup_calls = 0

    def export(self, items: Sequence[CatalogItem]) -> list[Path]:
        _ = items
        self.export_calls += 1
        return list(self._export_result)

    def cleanup(self) -> list[Path]:
        self.cleanup_calls += 1
        return list(self._cleanup_result)


def test_export_outputs_given_disabled_target_when_run_then_cleans_stale_output():
    logger = _FakeLogger()
    hb_exporter = _FakeExporter(
        target=OutputTarget.HB_STORE,
        export_result=[Path("/tmp/store.db")],
        cleanup_result=[],
    )
    fpkgi_exporter = _FakeExporter(
        target=OutputTarget.FPKGI,
        export_result=[Path("/tmp/GAMES.json")],
        cleanup_result=[Path("/tmp/GAMES.json"), Path("/tmp/DLC.json")],
    )

    use_case = ExportOutputs(
        uow_factory=lambda: _FakeUnitOfWork(items=[]),
        exporters=[hb_exporter, fpkgi_exporter],
        logger=logger,
    )

    exported = use_case((OutputTarget.HB_STORE,))

    assert exported == (Path("/tmp/store.db"),)
    assert hb_exporter.export_calls == 1
    assert hb_exporter.cleanup_calls == 0
    assert fpkgi_exporter.export_calls == 0
    assert fpkgi_exporter.cleanup_calls == 1
    assert (
        "Saida desativada removida: destino: fpkgi, arquivos: 2"
        in logger.infos
    )
