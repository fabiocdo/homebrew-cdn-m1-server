import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.utils.db_utils import DBUtils
from hb_store_m1.utils.init_utils import InitUtils


def test_given_path_outside_data_when_upsert_then_writes_original(
    init_paths, tmp_path
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(
        init_sql, encoding="utf-8"
    )

    InitUtils.init_db()

    other_path = tmp_path / "other.bin"
    other_path.write_text("data", encoding="utf-8")
    icon_path = init_paths.MEDIA_DIR_PATH / "content_icon0.png"
    icon_path.write_text("png", encoding="utf-8")

    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        icon0_png_path=icon_path,
        pkg_path=other_path,
    )

    result = DBUtils.upsert([pkg])
    assert result.status.name == "OK"

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    try:
        row = conn.execute(
            "SELECT package FROM homebrews WHERE content_id=?",
            (pkg.content_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == urljoin(Globals.ENVS.SERVER_URL, str(other_path))


def test_given_pkg_when_upsert_then_writes_cdn_urls_and_md5(init_paths, tmp_path):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(
        init_sql, encoding="utf-8"
    )

    InitUtils.init_db()

    pkg_path = init_paths.GAME_DIR_PATH / "content.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    icon_path = init_paths.MEDIA_DIR_PATH / "content_icon0.png"
    icon_path.write_text("png", encoding="utf-8")
    pic0_path = init_paths.MEDIA_DIR_PATH / "content_pic0.png"
    pic0_path.write_text("png", encoding="utf-8")
    pic1_path = init_paths.MEDIA_DIR_PATH / "content_pic1.png"
    pic1_path.write_text("png", encoding="utf-8")

    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        icon0_png_path=icon_path,
        pic0_png_path=pic0_path,
        pic1_png_path=pic1_path,
        pkg_path=pkg_path,
    )

    result = DBUtils.upsert([pkg])
    assert result.status.name == "OK"

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    try:
        row = conn.execute(
            "SELECT package, image, main_icon_path, main_menu_pic, row_md5 FROM homebrews"
        ).fetchone()
    finally:
        conn.close()

    expected_pkg_url = urljoin(Globals.ENVS.SERVER_URL, str(pkg_path))
    expected_icon_url = urljoin(Globals.ENVS.SERVER_URL, str(icon_path))
    expected_pic0_url = urljoin(Globals.ENVS.SERVER_URL, str(pic0_path))
    expected_pic1_url = urljoin(Globals.ENVS.SERVER_URL, str(pic1_path))

    assert row[0] == expected_pkg_url
    assert row[1] == expected_icon_url
    assert row[2] == expected_pic0_url
    assert row[3] == expected_pic1_url
    assert row[4]
