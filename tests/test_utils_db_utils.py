import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.utils.db_utils import DBUtils
from hb_store_m1.utils.init_utils import InitUtils


def test_given_path_outside_data_when_upsert_then_writes_canonical_pkg_url(
    init_paths, tmp_path
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")

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

    assert row[0] == urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )


def test_given_pkg_when_upsert_then_writes_cdn_urls_and_md5(init_paths, tmp_path):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")

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
            "SELECT package, image, picpath, main_icon_path, main_menu_pic, row_md5, apptype FROM homebrews"
        ).fetchone()
    finally:
        conn.close()

    expected_pkg_url = urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )
    expected_icon_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
    )
    expected_pic0_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_pic0.png",
    )
    expected_pic1_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_pic1.png",
    )

    assert row[0] == expected_pkg_url
    assert row[1] == expected_icon_url
    assert (
        row[2]
        == "/user/app/NPXS39041/storedata/UP0000-TEST00000_00-TEST000000000000_icon0.png"
    )
    assert row[3] == expected_pic0_url
    assert row[4] == expected_pic1_url
    assert row[5]
    assert row[6] == "Game"


def test_given_old_urls_when_refresh_urls_then_rewrites_base_and_pkg_path(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    old_server = "http://10.0.0.10:8080"
    content_id = "UP0000-TEST00000_00-TEST000000000000"

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    conn.execute(
        """
        INSERT INTO homebrews (
            content_id, id, name, desc, image, package, version, picpath, desc_1, desc_2,
            ReviewStars, Size, Author, apptype, pv, main_icon_path, main_menu_pic, releaseddate,
            number_of_downloads, github, video, twitter, md5, row_md5
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_id,
            "CUSA00001",
            "Test",
            None,
            f"{old_server}/app/data/pkg/_media/{content_id}_icon0.png",
            f"{old_server}/app/data/pkg/game/{content_id}.pkg",
            "01.00",
            f"{old_server}/app/data/pkg/_media/{content_id}_pic0.png",
            None,
            None,
            None,
            1,
            None,
            "game",
            None,
            f"{old_server}/app/data/pkg/_media/{content_id}_pic0.png",
            f"{old_server}/app/data/pkg/_media/{content_id}_pic0.png",
            "2024-01-01",
            0,
            None,
            None,
            None,
            None,
            "old-md5",
        ),
    )
    conn.commit()
    conn.close()

    result = DBUtils.refresh_urls()

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    row = conn.execute(
        "SELECT package, image, picpath, main_icon_path, main_menu_pic, row_md5, apptype FROM homebrews WHERE content_id = ?",
        (content_id,),
    ).fetchone()
    conn.close()

    assert result.status is Status.OK
    assert row[0] == urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")
    assert row[1] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_icon0.png"
    )
    assert row[2] == f"/user/app/NPXS39041/storedata/{content_id}_icon0.png"
    assert row[3] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_pic0.png"
    )
    assert row[4] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_pic1.png"
    )
    assert row[5] != "old-md5"
    assert row[6] == "Game"


def test_given_pkg_categories_when_upsert_then_maps_apptype_to_ps4_store_labels(
    init_paths,
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    patch_pkg_path = init_paths.UPDATE_DIR_PATH / "patch.pkg"
    patch_pkg_path.write_text("data", encoding="utf-8")
    save_pkg_path = init_paths.UNKNOWN_DIR_PATH / "save.pkg"
    save_pkg_path.write_text("data", encoding="utf-8")

    patch_pkg = PKG(
        title="Patch",
        title_id="CUSA00002",
        content_id="UP0000-TEST00002_00-TEST000000000002",
        category="GP",
        version="01.01",
        pkg_path=patch_pkg_path,
    )
    save_pkg = PKG(
        title="Save",
        title_id="CUSA00003",
        content_id="UP0000-TEST00003_00-TEST000000000003",
        category="SD",
        version="01.01",
        pkg_path=save_pkg_path,
    )

    result = DBUtils.upsert([patch_pkg, save_pkg])
    assert result.status is Status.OK

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    rows = conn.execute(
        "SELECT content_id, apptype, package FROM homebrews WHERE content_id IN (?, ?)",
        (patch_pkg.content_id, save_pkg.content_id),
    ).fetchall()
    conn.close()
    by_content_id = {row[0]: row for row in rows}

    assert by_content_id[patch_pkg.content_id][1] == "Patch"
    assert by_content_id[patch_pkg.content_id][2] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/update/{patch_pkg.content_id}.pkg"
    )
    assert by_content_id[save_pkg.content_id][1] == "Other"


def test_given_existing_rows_when_select_content_ids_then_returns_values(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg_path = init_paths.GAME_DIR_PATH / "content.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )
    DBUtils.upsert([pkg])

    result = DBUtils.select_content_ids()

    assert result.status is Status.OK
    assert pkg.content_id in (result.content or [])


def test_given_conn_none_when_select_by_content_ids_then_opens_connection(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg_path = init_paths.GAME_DIR_PATH / "content.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )
    DBUtils.upsert([pkg])

    result = DBUtils.select_by_content_ids(None, [pkg.content_id])

    assert result.status is Status.OK
    assert (result.content or [])[0]["content_id"] == pkg.content_id


def test_given_unchanged_pkg_when_upsert_then_returns_skip(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg_path = init_paths.GAME_DIR_PATH / "content.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )

    first = DBUtils.upsert([pkg])
    second = DBUtils.upsert([pkg])

    assert first.status is Status.OK
    assert second.status is Status.SKIP


def test_given_content_ids_when_delete_then_deletes_rows(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg_path = init_paths.GAME_DIR_PATH / "content.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="Test",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )
    DBUtils.upsert([pkg])

    result = DBUtils.delete_by_content_ids([pkg.content_id])
    remaining = DBUtils.select_content_ids().content or []

    assert result.status is Status.OK
    assert pkg.content_id not in remaining


def test_given_pid_gaps_when_refresh_urls_then_compacts_pid_sequence(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg1_path = init_paths.GAME_DIR_PATH / "content1.pkg"
    pkg1_path.write_text("data", encoding="utf-8")
    pkg2_path = init_paths.GAME_DIR_PATH / "content2.pkg"
    pkg2_path.write_text("data", encoding="utf-8")

    pkg1 = PKG(
        title="Test 1",
        title_id="CUSA00001",
        content_id="UP0000-TEST00001_00-TEST000000000001",
        category="GD",
        version="01.00",
        pkg_path=pkg1_path,
    )
    pkg2 = PKG(
        title="Test 2",
        title_id="CUSA00002",
        content_id="UP0000-TEST00002_00-TEST000000000002",
        category="GD",
        version="01.00",
        pkg_path=pkg2_path,
    )
    DBUtils.upsert([pkg1, pkg2])

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    conn.execute("DELETE FROM homebrews WHERE content_id = ?", (pkg1.content_id,))
    conn.commit()
    before = conn.execute(
        "SELECT pid, content_id FROM homebrews ORDER BY pid"
    ).fetchall()
    conn.close()
    assert before == [(2, pkg2.content_id)]

    result = DBUtils.refresh_urls()

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    after = conn.execute(
        "SELECT pid, content_id FROM homebrews ORDER BY pid"
    ).fetchall()
    conn.close()

    assert result.status is Status.OK
    assert after == [(1, pkg2.content_id)]


def test_given_deleted_rows_when_delete_then_compacts_pid_sequence(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    pkg1_path = init_paths.GAME_DIR_PATH / "content1.pkg"
    pkg1_path.write_text("data", encoding="utf-8")
    pkg2_path = init_paths.GAME_DIR_PATH / "content2.pkg"
    pkg2_path.write_text("data", encoding="utf-8")
    pkg3_path = init_paths.GAME_DIR_PATH / "content3.pkg"
    pkg3_path.write_text("data", encoding="utf-8")

    pkg1 = PKG(
        title="Test 1",
        title_id="CUSA00001",
        content_id="UP0000-TEST00001_00-TEST000000000001",
        category="GD",
        version="01.00",
        pkg_path=pkg1_path,
    )
    pkg2 = PKG(
        title="Test 2",
        title_id="CUSA00002",
        content_id="UP0000-TEST00002_00-TEST000000000002",
        category="GD",
        version="01.00",
        pkg_path=pkg2_path,
    )
    pkg3 = PKG(
        title="Test 3",
        title_id="CUSA00003",
        content_id="UP0000-TEST00003_00-TEST000000000003",
        category="GD",
        version="01.00",
        pkg_path=pkg3_path,
    )
    DBUtils.upsert([pkg1, pkg2, pkg3])

    result = DBUtils.delete_by_content_ids([pkg2.content_id])

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    rows = conn.execute("SELECT pid, content_id FROM homebrews ORDER BY pid").fetchall()
    conn.close()

    assert result.status is Status.OK
    assert result.content == 1
    assert rows == [(1, pkg1.content_id), (2, pkg3.content_id)]


def test_given_valid_game_and_patch_when_sanity_check_then_returns_ok(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    game_pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    game_pkg_path.write_text("data", encoding="utf-8")
    patch_pkg_path = init_paths.UPDATE_DIR_PATH / "patch.pkg"
    patch_pkg_path.write_text("data", encoding="utf-8")

    game_pkg = PKG(
        title="Game",
        title_id="CUSA10001",
        content_id="UP0000-TEST10001_00-TEST000000001001",
        category="GD",
        version="01.00",
        pkg_path=game_pkg_path,
    )
    patch_pkg = PKG(
        title="Patch",
        title_id="CUSA10002",
        content_id="UP0000-TEST10002_00-TEST000000001002",
        category="GP",
        version="01.00",
        pkg_path=patch_pkg_path,
    )
    DBUtils.upsert([game_pkg, patch_pkg])

    result = DBUtils.sanity_check()

    assert result.status is Status.OK
    assert (result.content or {}).get("missing_by_type") == {}
    assert (result.content or {}).get("has_pid_gaps") is False


def test_given_missing_game_fields_when_sanity_check_then_returns_warn(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    content_id = "UP0000-TEST20001_00-TEST000000002001"
    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    conn.execute(
        """
        INSERT INTO homebrews (
            content_id, id, name, desc, image, package, version, picpath, desc_1, desc_2,
            ReviewStars, Size, Author, apptype, pv, main_icon_path, main_menu_pic, releaseddate,
            number_of_downloads, github, video, twitter, md5, row_md5
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_id,
            "CUSA20001",
            "Broken Game",
            None,
            "",
            "http://example/pkg/game.pkg",
            "01.00",
            None,
            None,
            None,
            None,
            1,
            None,
            "Game",
            None,
            None,
            None,
            "2024-01-01",
            0,
            None,
            None,
            None,
            None,
            "row",
        ),
    )
    conn.commit()
    conn.close()

    result = DBUtils.sanity_check()
    summary = result.content or {}

    assert result.status is Status.WARN
    assert summary["missing_by_type"]["Game"]["image"] == 1
    assert summary["missing_by_type"]["Game"]["picpath"] == 1


def test_given_missing_db_when_delete_then_returns_not_found(temp_globals):
    result = DBUtils.delete_by_content_ids(["X"])

    assert result.status is Status.NOT_FOUND


def test_given_empty_content_ids_when_delete_then_returns_skip(init_paths):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    result = DBUtils.delete_by_content_ids([])

    assert result.status is Status.SKIP


def test_given_db_error_when_select_content_ids_then_returns_error(
    init_paths, monkeypatch
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    class _BadCursor:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.Error("boom")

    class _BadConn:
        def cursor(self):
            return _BadCursor()

        def close(self):
            return None

    monkeypatch.setattr(DBUtils, "_connect", lambda: _BadConn())

    result = DBUtils.select_content_ids()

    assert result.status is Status.ERROR


def test_given_db_error_when_delete_then_returns_error(init_paths, monkeypatch):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()

    class _BadConn:
        total_changes = 0

        def execute(self, *_args, **_kwargs):
            return None

        def executemany(self, *_args, **_kwargs):
            raise sqlite3.Error("boom")

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(DBUtils, "_connect", lambda: _BadConn())

    result = DBUtils.delete_by_content_ids(["X"])

    assert result.status is Status.ERROR
