# pyright: reportPrivateUsage=false

from __future__ import annotations

import sqlite3
from pathlib import Path
import signal
from typing import cast

import pytest

from homebrew_cdn_m1_server.application import app as app_module
from homebrew_cdn_m1_server.application.app import WorkerApp
from homebrew_cdn_m1_server.application.gateways.github_assets_gateway import (
    GithubAssetsGateway,
)
from homebrew_cdn_m1_server.config.settings_loader import SettingsLoader
from homebrew_cdn_m1_server.domain.models.app_config import AppConfig
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.results import ReconcileResult


def _load_config(temp_workspace: Path, settings: str = "") -> AppConfig:
    settings_path = temp_workspace / "configs" / "settings.ini"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(settings, encoding="utf-8")
    snapshot_src = Path(__file__).resolve().parents[1] / "init" / "snapshot.schema.json"
    snapshot_dst = temp_workspace / "init" / "snapshot.schema.json"
    snapshot_dst.parent.mkdir(parents=True, exist_ok=True)
    _ = snapshot_dst.write_text(snapshot_src.read_text("utf-8"), encoding="utf-8")
    return SettingsLoader.load(settings_path)


class _FakeScheduler:
    def __init__(self) -> None:
        self.cron_calls: list[tuple[str, str]] = []
        self.interval_calls: list[tuple[str, int]] = []
        self.started: bool = False
        self.stopped: bool = False

    def schedule_cron(self, job_id: str, cron_expression: str, _func: object) -> None:
        self.cron_calls.append((job_id, cron_expression))

    def schedule_interval(self, job_id: str, seconds: int, _func: object) -> None:
        self.interval_calls.append((job_id, seconds))

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True


class _FakeReconcile:
    def __init__(self) -> None:
        self.calls: int = 0

    def __call__(self) -> ReconcileResult:
        self.calls += 1
        return ReconcileResult(added=0, updated=0, removed=0, failed=0, exported_files=tuple())


class _FakeGithubAssetsGateway:
    def __init__(self) -> None:
        self.calls: list[list[Path]] = []
        self.to_download: list[Path] = []
        self.to_missing: list[Path] = []
        self.should_raise: bool = False

    def download_latest_release_assets(
        self, destinations: list[Path]
    ) -> tuple[list[Path], list[Path]]:
        self.calls.append(destinations)
        if self.should_raise:
            raise RuntimeError("upstream failed")
        return self.to_download, self.to_missing


def test_worker_app_read_init_sql_given_missing_when_called_then_raises(
    temp_workspace: Path,
) -> None:
    missing = temp_workspace / "init" / "catalog_db.sql"
    with pytest.raises(FileNotFoundError, match="Catalog schema not found"):
        _ = WorkerApp._read_init_sql(missing)


def test_worker_app_read_init_sql_given_empty_when_called_then_raises(
    temp_workspace: Path,
) -> None:
    schema = temp_workspace / "init" / "catalog_db.sql"
    _ = schema.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Catalog schema file is empty"):
        _ = WorkerApp._read_init_sql(schema)


def test_worker_app_read_init_sql_given_content_when_called_then_returns_trimmed_sql(
    temp_workspace: Path,
) -> None:
    schema = temp_workspace / "init" / "catalog_db.sql"
    _ = schema.write_text("  CREATE TABLE t(a INT);  \n", encoding="utf-8")
    assert WorkerApp._read_init_sql(schema) == "CREATE TABLE t(a INT);"


def test_worker_app_initialize_layout_and_schema_given_valid_init_when_called_then_prepares_runtime(
    temp_workspace: Path,
) -> None:
    _ = (temp_workspace / "init" / "index.html").write_text("<html></html>", encoding="utf-8")
    _ = (temp_workspace / "init" / "catalog_db.sql").write_text(
        "CREATE TABLE IF NOT EXISTS test_init (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    config = _load_config(temp_workspace)
    app = WorkerApp(config)

    app._initialize_layout_and_schema()

    assert config.paths.catalog_db_path.exists() is True
    assert config.paths.public_index_path.exists() is True
    with sqlite3.connect(config.paths.catalog_db_path) as conn:
        rows = cast(
            list[tuple[str]],
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_init'"
            ).fetchall(),
        )
        names = [row[0] for row in rows]
    assert names == ["test_init"]


def test_worker_app_build_reconcile_use_case_given_config_when_called_then_wires_dependencies(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_config(temp_workspace)
    app = WorkerApp(config)
    captures: dict[str, object] = {}

    class _FakeIngestPackage:
        def __init__(self, **kwargs: object) -> None:
            captures["ingest"] = kwargs

    class _FakeStoreDbExporter:
        def __init__(self, **kwargs: object) -> None:
            captures["store_exporter"] = kwargs

    class _FakeFpkgiExporter:
        def __init__(self, **kwargs: object) -> None:
            captures["fpkgi_exporter"] = kwargs

    class _FakeExportOutputs:
        def __init__(self, **kwargs: object) -> None:
            captures["export"] = kwargs

    class _FakeReconcileCatalog:
        def __init__(self, **kwargs: object) -> None:
            captures["reconcile"] = kwargs

    monkeypatch.setattr(app_module, "IngestPackage", _FakeIngestPackage)
    monkeypatch.setattr(app_module, "StoreDbExporter", _FakeStoreDbExporter)
    monkeypatch.setattr(app_module, "FpkgiJsonExporter", _FakeFpkgiExporter)
    monkeypatch.setattr(app_module, "ExportOutputs", _FakeExportOutputs)
    monkeypatch.setattr(app_module, "ReconcileCatalog", _FakeReconcileCatalog)

    _ = app._build_reconcile_use_case()

    assert "ingest" in captures
    assert "store_exporter" in captures
    assert "fpkgi_exporter" in captures
    assert "export" in captures
    assert "reconcile" in captures
    reconcile_kwargs = captures["reconcile"]
    assert isinstance(reconcile_kwargs, dict)
    assert reconcile_kwargs["worker_count"] == (
        config.user.reconcile_pkg_preprocess_workers
        if config.user.reconcile_pkg_preprocess_workers is not None
        else 1
    )
    assert reconcile_kwargs["output_targets"] == (config.user.output_targets or tuple())


def test_worker_app_start_given_cron_expression_when_called_then_schedules_cron(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_config(temp_workspace, "RECONCILE_CRON_EXPRESSION=*/5 * * * *\n")
    app = WorkerApp(config)
    fake_scheduler = _FakeScheduler()
    fake_reconcile = _FakeReconcile()

    def _scheduler_factory() -> _FakeScheduler:
        return fake_scheduler

    def _build_reconcile() -> _FakeReconcile:
        return fake_reconcile

    monkeypatch.setattr(app_module, "APSchedulerRunner", _scheduler_factory)
    monkeypatch.setattr(app, "_initialize_layout_and_schema", lambda: None)
    monkeypatch.setattr(app, "_sync_hb_store_assets_on_startup", lambda: None)
    monkeypatch.setattr(app, "_build_reconcile_use_case", _build_reconcile)

    app.start()

    assert fake_reconcile.calls == 1
    assert fake_scheduler.cron_calls == [("reconcile", "*/5 * * * *")]
    assert fake_scheduler.interval_calls == []
    assert fake_scheduler.started is True

    app.shutdown()
    assert fake_scheduler.stopped is True


def test_worker_app_start_given_empty_cron_when_called_then_schedules_interval(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_config(temp_workspace, "RECONCILE_CRON_EXPRESSION=\n")
    config = AppConfig(
        user=config.user.model_copy(update={"reconcile_cron_expression": ""}),
        paths=config.paths,
        reconcile_interval_seconds=45,
        reconcile_file_stable_seconds=config.reconcile_file_stable_seconds,
    )
    app = WorkerApp(config)
    fake_scheduler = _FakeScheduler()
    fake_reconcile = _FakeReconcile()

    def _scheduler_factory() -> _FakeScheduler:
        return fake_scheduler

    def _build_reconcile() -> _FakeReconcile:
        return fake_reconcile

    monkeypatch.setattr(app_module, "APSchedulerRunner", _scheduler_factory)
    monkeypatch.setattr(app, "_initialize_layout_and_schema", lambda: None)
    monkeypatch.setattr(app, "_sync_hb_store_assets_on_startup", lambda: None)
    monkeypatch.setattr(app, "_build_reconcile_use_case", _build_reconcile)

    app.start()

    assert fake_reconcile.calls == 1
    assert fake_scheduler.cron_calls == []
    assert fake_scheduler.interval_calls == [("reconcile", 45)]


def test_worker_app_shutdown_given_no_scheduler_when_called_then_noop(
    temp_workspace: Path,
) -> None:
    app = WorkerApp(_load_config(temp_workspace))
    app.shutdown()


def test_worker_app_run_given_stop_requested_when_called_then_returns_zero(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = WorkerApp(_load_config(temp_workspace))
    state = {"start_called": False, "shutdown_called": False}
    handlers: dict[int, object] = {}

    def _fake_start() -> None:
        state["start_called"] = True
        setattr(app, "_should_stop", True)

    def _fake_shutdown() -> None:
        state["shutdown_called"] = True

    def _fake_signal(signum: int, handler: object) -> object:
        handlers[signum] = handler
        return object()

    monkeypatch.setattr(app, "start", _fake_start)
    monkeypatch.setattr(app, "shutdown", _fake_shutdown)
    monkeypatch.setattr(signal, "signal", _fake_signal)

    code = app.run()

    assert code == 0
    assert state == {"start_called": True, "shutdown_called": True}
    assert signal.SIGTERM in handlers
    assert signal.SIGINT in handlers


def test_worker_app_run_from_env_given_settings_file_when_called_then_loads_and_runs(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = temp_workspace / "configs" / "custom.ini"
    _ = settings_path.write_text("", encoding="utf-8")
    config = _load_config(temp_workspace)
    observed: dict[str, object] = {}

    def _fake_load(
        _cls: type[SettingsLoader],
        path: Path | None = None,
    ) -> AppConfig:
        observed["settings_path"] = path
        return config

    def _fake_configure(level: str | None, error_log_path: Path) -> None:
        observed["log_level"] = level
        observed["error_log_path"] = error_log_path

    def _fake_run(_self: WorkerApp) -> int:
        observed["ran"] = True
        return 7

    monkeypatch.setenv("SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(SettingsLoader, "load", classmethod(_fake_load))
    monkeypatch.setattr(app_module, "configure_logging", _fake_configure)
    monkeypatch.setattr(app_module.WorkerApp, "run", _fake_run)

    exit_code = WorkerApp.run_from_env()

    assert exit_code == 7
    assert observed["settings_path"] == settings_path
    assert observed["log_level"] == config.user.log_level
    assert observed["error_log_path"] == config.paths.logs_dir / "app_errors.log"
    assert observed["ran"] is True


def test_worker_app_run_from_env_given_default_path_when_called_then_uses_none(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_config(temp_workspace)
    observed: dict[str, object] = {}

    def _fake_load(
        _cls: type[SettingsLoader],
        path: Path | None = None,
    ) -> AppConfig:
        observed["settings_path"] = path
        return config

    def _fake_configure(level: str | None, error_log_path: Path) -> None:
        _ = (level, error_log_path)

    def _fake_run(_self: WorkerApp) -> int:
        return 0

    monkeypatch.delenv("SETTINGS_FILE", raising=False)
    monkeypatch.setattr(SettingsLoader, "load", classmethod(_fake_load))
    monkeypatch.setattr(app_module, "configure_logging", _fake_configure)
    monkeypatch.setattr(app_module.WorkerApp, "run", _fake_run)

    _ = WorkerApp.run_from_env()
    assert observed["settings_path"] is None


def test_worker_app_build_reconcile_use_case_given_targets_when_passed_then_preserves_order(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_config(temp_workspace)
    config = AppConfig(
        user=config.user.model_copy(
            update={"output_targets": (OutputTarget.FPKGI, OutputTarget.HB_STORE)}
        ),
        paths=config.paths,
        reconcile_interval_seconds=config.reconcile_interval_seconds,
        reconcile_file_stable_seconds=config.reconcile_file_stable_seconds,
    )
    app = WorkerApp(config)
    captures: dict[str, object] = {}

    class _FakeIngestPackage:
        def __init__(self, **kwargs: object) -> None:
            _ = kwargs

    class _FakeStoreDbExporter:
        def __init__(self, **kwargs: object) -> None:
            _ = kwargs

    class _FakeFpkgiExporter:
        def __init__(self, **kwargs: object) -> None:
            _ = kwargs

    class _FakeExportOutputs:
        def __init__(self, **kwargs: object) -> None:
            _ = kwargs

    class _FakeReconcileCatalog:
        def __init__(self, **kwargs: object) -> None:
            captures["output_targets"] = kwargs.get("output_targets")

    monkeypatch.setattr(app_module, "IngestPackage", _FakeIngestPackage)
    monkeypatch.setattr(app_module, "StoreDbExporter", _FakeStoreDbExporter)
    monkeypatch.setattr(app_module, "FpkgiJsonExporter", _FakeFpkgiExporter)
    monkeypatch.setattr(app_module, "ExportOutputs", _FakeExportOutputs)
    monkeypatch.setattr(app_module, "ReconcileCatalog", _FakeReconcileCatalog)

    _ = app._build_reconcile_use_case()
    assert captures["output_targets"] == (OutputTarget.FPKGI, OutputTarget.HB_STORE)


def test_worker_app_sync_hb_store_assets_given_target_disabled_when_called_then_skips_download(
    temp_workspace: Path,
) -> None:
    config = _load_config(temp_workspace)
    config = AppConfig(
        user=config.user.model_copy(update={"output_targets": (OutputTarget.FPKGI,)}),
        paths=config.paths,
        reconcile_interval_seconds=config.reconcile_interval_seconds,
        reconcile_file_stable_seconds=config.reconcile_file_stable_seconds,
    )
    app = WorkerApp(config)
    fake_gateway = _FakeGithubAssetsGateway()
    app._github_assets = cast(GithubAssetsGateway, cast(object, fake_gateway))

    app._sync_hb_store_assets_on_startup()

    assert fake_gateway.calls == []


def test_worker_app_sync_hb_store_assets_given_target_enabled_when_called_then_downloads_expected_assets(
    temp_workspace: Path,
) -> None:
    config = _load_config(temp_workspace)
    config = AppConfig(
        user=config.user.model_copy(update={"output_targets": (OutputTarget.HB_STORE,)}),
        paths=config.paths,
        reconcile_interval_seconds=config.reconcile_interval_seconds,
        reconcile_file_stable_seconds=config.reconcile_file_stable_seconds,
    )
    app = WorkerApp(config)
    fake_gateway = _FakeGithubAssetsGateway()
    app._github_assets = cast(GithubAssetsGateway, cast(object, fake_gateway))

    app._sync_hb_store_assets_on_startup()

    assert len(fake_gateway.calls) == 1
    requested = fake_gateway.calls[0]
    assert requested == [
        config.paths.hb_store_update_dir / "remote.md5",
        config.paths.hb_store_update_dir / "homebrew.elf",
        config.paths.hb_store_update_dir / "homebrew.elf.sig",
    ]


def test_worker_app_sync_hb_store_assets_given_gateway_error_when_called_then_continues(
    temp_workspace: Path,
) -> None:
    config = _load_config(temp_workspace)
    config = AppConfig(
        user=config.user.model_copy(update={"output_targets": (OutputTarget.HB_STORE,)}),
        paths=config.paths,
        reconcile_interval_seconds=config.reconcile_interval_seconds,
        reconcile_file_stable_seconds=config.reconcile_file_stable_seconds,
    )
    app = WorkerApp(config)
    fake_gateway = _FakeGithubAssetsGateway()
    fake_gateway.should_raise = True
    app._github_assets = cast(GithubAssetsGateway, cast(object, fake_gateway))

    app._sync_hb_store_assets_on_startup()

    assert len(fake_gateway.calls) == 1
