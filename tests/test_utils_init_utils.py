import sqlite3
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Output, Status
from hb_store_m1.utils import init_utils as init_utils_module
from hb_store_m1.utils.init_utils import InitUtils


def test_given_empty_directories_when_init_directories_then_creates_all(temp_globals):
    InitUtils.init_directories()

    for path in vars(Globals.PATHS).values():
        assert path.exists()


def test_given_store_db_script_when_init_db_then_creates_database(
    init_paths,
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")

    InitUtils.init_db()

    assert Globals.FILES.STORE_DB_FILE_PATH.exists()


def test_given_assets_when_init_assets_then_handles_missing(monkeypatch, temp_globals):
    def fake_download(_assets):
        return [], [_assets[0]]

    monkeypatch.setattr(
        "hb_store_m1.utils.init_utils.StoreAssetClient.download_store_assets",
        fake_download,
    )

    InitUtils.init_assets()


def test_given_assets_when_init_assets_then_logs_ok(monkeypatch, temp_globals):
    monkeypatch.setattr(
        "hb_store_m1.utils.init_utils.StoreAssetClient.download_store_assets",
        lambda _assets: (list(_assets), []),
    )

    InitUtils.init_assets()


def test_given_download_error_when_init_assets_then_handles_exception(
    monkeypatch, temp_globals
):
    monkeypatch.setattr(
        "hb_store_m1.utils.init_utils.StoreAssetClient.download_store_assets",
        lambda _assets: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    InitUtils.init_assets()


def test_given_init_all_when_called_then_runs_all_init_steps(monkeypatch):
    called = {"dirs": 0, "db": 0, "assets": 0}

    monkeypatch.setattr(
        InitUtils,
        "init_directories",
        lambda: called.__setitem__("dirs", called["dirs"] + 1),
    )
    monkeypatch.setattr(
        InitUtils,
        "init_db",
        lambda: called.__setitem__("db", called["db"] + 1),
    )
    monkeypatch.setattr(
        InitUtils,
        "init_assets",
        lambda: called.__setitem__("assets", called["assets"] + 1),
    )

    InitUtils.init_all()

    assert called == {"dirs": 1, "db": 1, "assets": 1}


def test_given_sync_runtime_urls_when_called_then_refreshes_db_and_json(monkeypatch):
    called = {"db": 0, "json": 0, "sanity": 0}

    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.refresh_urls",
        lambda: called.__setitem__("db", called["db"] + 1) or Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.sync_from_store_db",
        lambda: called.__setitem__("json", called["json"] + 1) or Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.sanity_check",
        lambda: called.__setitem__("sanity", called["sanity"] + 1)
        or Output(Status.OK, {}),
    )

    InitUtils.sync_runtime_urls()

    assert called == {"db": 1, "json": 1, "sanity": 1}


def test_given_existing_db_when_init_db_then_returns_early(init_paths):
    db_path = Globals.FILES.STORE_DB_FILE_PATH
    db_path.write_text("already-there", encoding="utf-8")

    InitUtils.init_db()

    assert db_path.exists()


def test_given_sqlite_error_when_init_db_then_handles_error(init_paths, monkeypatch):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.Error("boom")),
    )

    InitUtils.init_db()

    assert not Globals.FILES.STORE_DB_FILE_PATH.exists()


def test_given_sync_runtime_urls_error_when_called_then_logs_warnings(monkeypatch):
    called = {"warn": 0}

    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.refresh_urls",
        lambda: Output(Status.ERROR, 0),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.sync_from_store_db",
        lambda: Output(Status.ERROR, 0),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.sanity_check",
        lambda: Output(Status.ERROR, {}),
    )
    monkeypatch.setattr(
        init_utils_module.log,
        "log_warn",
        lambda _msg: called.__setitem__("warn", called["warn"] + 1),
    )

    InitUtils.sync_runtime_urls()

    assert called["warn"] == 3


def test_given_sync_runtime_urls_when_sanity_warn_then_logs_warning(monkeypatch):
    called = {"warn": 0}

    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.refresh_urls",
        lambda: Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.sync_from_store_db",
        lambda: Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.sanity_check",
        lambda: Output(
            Status.WARN,
            {
                "app_type_counts": {"Game": 0, "Patch": 0},
                "missing_by_type": {"Game": {"image": 1}},
                "has_pid_gaps": False,
            },
        ),
    )
    monkeypatch.setattr(
        init_utils_module.log,
        "log_warn",
        lambda _msg: called.__setitem__("warn", called["warn"] + 1),
    )

    InitUtils.sync_runtime_urls()

    assert called["warn"] == 1
