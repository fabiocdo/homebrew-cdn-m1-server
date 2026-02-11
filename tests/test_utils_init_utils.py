from pathlib import Path

from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.models.globals import Globals


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
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(
        init_sql, encoding="utf-8"
    )

    InitUtils.init_db()

    assert Globals.FILES.STORE_DB_FILE_PATH.exists()


def test_given_template_json_when_init_template_json_then_creates_index(
    init_paths,
):
    template_path = init_paths.INIT_DIR_PATH / "json_template.json"
    template_path.write_text('[{"id":"x"}]', encoding="utf-8")

    InitUtils.init_template_json()

    assert Globals.FILES.INDEX_JSON_FILE_PATH.exists()


def test_given_assets_when_init_assets_then_handles_missing(monkeypatch, temp_globals):
    def fake_download(_assets):
        return [], [_assets[0]]

    monkeypatch.setattr(
        "hb_store_m1.utils.init_utils.StoreAssetClient.download_store_assets",
        fake_download,
    )

    InitUtils.init_assets()
