from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Output, Status
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
    called = {"db": 0, "json": 0}

    monkeypatch.setattr(
        "hb_store_m1.utils.db_utils.DBUtils.refresh_urls",
        lambda: called.__setitem__("db", called["db"] + 1) or Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.refresh_urls",
        lambda: called.__setitem__("json", called["json"] + 1) or Output(Status.OK, 1),
    )

    InitUtils.sync_runtime_urls()

    assert called == {"db": 1, "json": 1}
