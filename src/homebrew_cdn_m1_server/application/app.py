from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path
from types import FrameType
from typing import final

from homebrew_cdn_m1_server.domain.models.app_config import AppConfig
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.workflows.export_outputs import ExportOutputs
from homebrew_cdn_m1_server.domain.workflows.ingest_package import IngestPackage
from homebrew_cdn_m1_server.domain.workflows.reconcile_catalog import ReconcileCatalog
from homebrew_cdn_m1_server.domain.protocols.scheduler_protocol import SchedulerProtocol
from homebrew_cdn_m1_server.application.exporters.fpkgi_json_exporter import FpkgiJsonExporter
from homebrew_cdn_m1_server.application.exporters.store_db_exporter import StoreDbExporter
from homebrew_cdn_m1_server.application.gateways.github_assets_gateway import (
    GithubAssetsGateway,
)
from homebrew_cdn_m1_server.application.gateways.orbispatches_gateway import (
    OrbisPatchesGateway,
)
from homebrew_cdn_m1_server.application.gateways.pkgtool_gateway import PkgtoolGateway
from homebrew_cdn_m1_server.application.repositories.filesystem_repository import (
    FilesystemRepository,
)
from homebrew_cdn_m1_server.application.repositories.json_snapshot_repository import (
    JsonSnapshotRepository,
)
from homebrew_cdn_m1_server.application.repositories.settings_snapshot_repository import (
    SettingsSnapshotRepository,
)
from homebrew_cdn_m1_server.application.hb_store_api import (
    HbStoreApiResolver,
    HbStoreApiServer,
)
from homebrew_cdn_m1_server.application.repositories.sqlite_unit_of_work import SqliteUnitOfWork
from homebrew_cdn_m1_server.application.scheduler.apscheduler_runner import APSchedulerRunner
from homebrew_cdn_m1_server.config.logging_setup import configure_logging
from homebrew_cdn_m1_server.config.settings_loader import SettingsLoader


@final
class WorkerApp:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._scheduler: SchedulerProtocol | None = None
        self._should_stop = False
        self._log = logging.getLogger("homebrew_cdn_m1_server.worker")

        self._package_store = FilesystemRepository(config.paths)
        self._snapshot_store = JsonSnapshotRepository(
            snapshot_path=config.paths.snapshot_path,
            schema_path=config.paths.init_dir / "snapshot.schema.json",
        )
        self._settings_snapshot_store = SettingsSnapshotRepository(
            snapshot_path=config.paths.settings_snapshot_path,
            settings_path=config.paths.settings_path,
        )
        self._pkgtool = PkgtoolGateway(
            pkgtool_bin=config.paths.pkgtool_bin_path,
            timeout_seconds=config.user.pkgtool_timeout_seconds,
            media_dir=config.paths.media_dir,
        )
        self._github_assets = GithubAssetsGateway()
        self._metadata_lookup = OrbisPatchesGateway()
        self._hb_store_resolver = HbStoreApiResolver(
            catalog_db_path=config.paths.catalog_db_path,
            store_db_path=config.paths.store_db_path,
            base_url=config.base_url,
        )
        self._hb_store_api = HbStoreApiServer(
            resolver=self._hb_store_resolver,
            logger=self._log,
        )

    @classmethod
    def run_from_env(cls) -> int:
        settings_file = os.getenv("SETTINGS_FILE")
        config = SettingsLoader.load(Path(settings_file) if settings_file else None)
        configure_logging(config.user.log_level, config.paths.logs_dir / "app_errors.log")
        return cls(config).run()

    def _uow_factory(self) -> SqliteUnitOfWork:
        return SqliteUnitOfWork(self._config.paths.catalog_db_path)

    def _initialize_layout_and_schema(self) -> None:
        self._package_store.ensure_layout()
        self._package_store.ensure_public_index(self._config.paths.init_dir / "index.html")
        init_sql = self._read_init_sql(self._config.paths.init_dir / "catalog_db.sql")
        with self._uow_factory() as uow:
            uow.catalog.init_schema(init_sql)
            uow.commit()

    @staticmethod
    def _read_init_sql(path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Catalog schema not found: {path}")
        sql = path.read_text("utf-8").strip()
        if not sql:
            raise ValueError(f"Catalog schema file is empty: {path}")
        return sql

    def _build_reconcile_use_case(self) -> ReconcileCatalog:
        ingest = IngestPackage(
            uow_factory=self._uow_factory,
            package_probe=self._pkgtool,
            package_store=self._package_store,
            logger=self._log,
            metadata_lookup=self._metadata_lookup,
        )

        exporters = [
            StoreDbExporter(
                output_db_path=self._config.paths.store_db_path,
                init_sql_path=self._config.paths.init_dir / "store_db.sql",
                base_url=self._config.base_url,
                metadata_lookup=self._metadata_lookup,
            ),
            FpkgiJsonExporter(
                output_dir=self._config.paths.fpkgi_share_dir,
                base_url=self._config.base_url,
                schema_path=self._config.paths.init_dir / "fpkgi.schema.json",
            ),
        ]

        export_outputs = ExportOutputs(
            uow_factory=self._uow_factory,
            exporters=exporters,
            logger=self._log,
        )

        return ReconcileCatalog(
            uow_factory=self._uow_factory,
            package_store=self._package_store,
            snapshot_store=self._snapshot_store,
            ingest_package=ingest,
            export_outputs=export_outputs,
            lock_path=self._config.paths.cache_dir / "reconcile.lock",
            lock_timeout_seconds=0.0,
            logger=self._log,
            worker_count=(
                self._config.user.reconcile_pkg_preprocess_workers
                if self._config.user.reconcile_pkg_preprocess_workers is not None
                else 1
            ),
            output_targets=self._config.user.output_targets or tuple(),
            settings_snapshot_store=self._settings_snapshot_store,
        )

    def _reload_runtime_settings(self) -> None:
        current = self._config
        try:
            loaded = SettingsLoader.load(current.paths.settings_path)
        except Exception as exc:
            self._log.warning("Runtime settings reload failed: %s", exc)
            return

        old_base_url = current.base_url
        self._config = AppConfig(
            user=loaded.user,
            paths=loaded.paths,
            reconcile_interval_seconds=current.reconcile_interval_seconds,
            reconcile_file_stable_seconds=current.reconcile_file_stable_seconds,
        )
        self._pkgtool = PkgtoolGateway(
            pkgtool_bin=self._config.paths.pkgtool_bin_path,
            timeout_seconds=self._config.user.pkgtool_timeout_seconds,
            media_dir=self._config.paths.media_dir,
        )
        self._hb_store_resolver.set_base_url(self._config.base_url)

        if self._config.base_url != old_base_url:
            self._log.info(
                "Base URL updated from settings.ini: '%s' -> '%s'",
                old_base_url,
                self._config.base_url,
            )

    def _run_reconcile_cycle(self) -> None:
        self._reload_runtime_settings()
        reconcile = self._build_reconcile_use_case()
        _ = reconcile()

    def _sync_hb_store_assets_on_startup(self) -> None:
        output_targets = self._config.user.output_targets or tuple()
        if OutputTarget.HB_STORE not in output_targets:
            self._log.debug("HB-Store startup asset sync skipped: target disabled")
            return

        destinations = [
            self._config.paths.hb_store_update_dir / "remote.md5",
            self._config.paths.hb_store_update_dir / "homebrew.elf",
            self._config.paths.hb_store_update_dir / "homebrew.elf.sig",
        ]
        try:
            downloaded, missing = self._github_assets.download_latest_release_assets(
                destinations
            )
        except Exception as exc:
            self._log.warning("HB-Store startup asset sync failed: %s", exc)
            return

        if downloaded:
            self._log.info("HB-Store startup assets downloaded: %d", len(downloaded))
        else:
            self._log.debug("HB-Store startup assets already available")

        if missing:
            missing_names = ", ".join(path.name for path in missing)
            self._log.warning(
                "HB-Store startup assets not found in GitHub release: %s",
                missing_names,
            )

    def start(self) -> None:
        self._initialize_layout_and_schema()
        self._start_hb_store_api()
        self._sync_hb_store_assets_on_startup()
        self._run_reconcile_cycle()

        scheduler = APSchedulerRunner()
        cron_expr = str(self._config.user.reconcile_cron_expression or "").strip()
        if cron_expr:
            scheduler.schedule_cron("reconcile", cron_expr, self._run_reconcile_cycle)
            self._log.info("Scheduler configured with cron: '%s'", cron_expr)
        else:
            scheduler.schedule_interval(
                "reconcile", self._config.reconcile_interval_seconds, self._run_reconcile_cycle
            )
            self._log.info(
                "Scheduler configured with %ss interval",
                self._config.reconcile_interval_seconds,
            )

        scheduler.start()
        self._scheduler = scheduler
        self._log.info("Service started")

    def _start_hb_store_api(self) -> None:
        self._hb_store_api.start()

    def run(self) -> int:
        self._install_signal_handlers()
        self.start()
        try:
            while not self._should_stop:
                time.sleep(0.5)
        finally:
            self.shutdown()
        return 0

    def shutdown(self) -> None:
        self._stop_hb_store_api()
        scheduler = self._scheduler
        if scheduler is None:
            return
        self._scheduler = None
        scheduler.shutdown()
        self._log.info("Service stopped")

    def _stop_hb_store_api(self) -> None:
        self._hb_store_api.stop()

    def _install_signal_handlers(self) -> None:
        def _stop_handler(_signum: int, _frame: FrameType | None) -> None:
            self._should_stop = True

        _ = signal.signal(signal.SIGTERM, _stop_handler)
        _ = signal.signal(signal.SIGINT, _stop_handler)
