import sqlite3
from pathlib import Path

from hb_store_m1.modules.http_api import (
    increment_downloads_by_content_id,
    lookup_pkg_by_tid,
    pkg_file_path,
    pkg_internal_path,
    pkg_redirect_path,
    store_db_hash,
)


def _create_homebrews_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE homebrews (
            pid INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT,
            content_id TEXT,
            apptype TEXT,
            package TEXT,
            number_of_downloads INTEGER
        );
        """)
    conn.commit()
    conn.close()


def test_given_store_db_when_hash_then_returns_md5(tmp_path):
    db_path = tmp_path / "store.db"
    db_path.write_bytes(b"hb-store")

    assert store_db_hash(db_path) == "75d2fe1517f2475ed65276d14df2c95f"


def test_given_tid_when_lookup_then_returns_row_by_id(tmp_path):
    db_path = tmp_path / "store.db"
    _create_homebrews_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO homebrews (id, content_id, apptype, package, number_of_downloads)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "CUSA00001",
            "UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP",
            "game",
            "http://host/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg",
            7,
        ),
    )
    conn.commit()
    conn.close()

    row = lookup_pkg_by_tid("cusa00001", db_path)

    assert row is not None
    assert row["id"] == "CUSA00001"
    assert row["number_of_downloads"] == 7


def test_given_content_id_when_lookup_then_returns_row(tmp_path):
    db_path = tmp_path / "store.db"
    _create_homebrews_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO homebrews (id, content_id, apptype, package, number_of_downloads)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "CUSA12345",
            "UP0000-CUSA12345_00-ABCDEFGHIJKLMNOP",
            "DLC",
            "http://host/pkg/dlc/UP0000-CUSA12345_00-ABCDEFGHIJKLMNOP.pkg",
            0,
        ),
    )
    conn.commit()
    conn.close()

    row = lookup_pkg_by_tid("UP0000-CUSA12345_00-ABCDEFGHIJKLMNOP", db_path)

    assert row is not None
    assert row["apptype"] == "DLC"


def test_given_valid_row_when_pkg_redirect_then_returns_pkg_path():
    entry = {
        "apptype": "game",
        "content_id": "UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP",
        "package": "http://host/app/data/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg",
    }

    assert (
        pkg_redirect_path(entry) == "/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg"
    )


def test_given_invalid_content_id_when_pkg_redirect_then_falls_back_to_package():
    entry = {
        "apptype": "game",
        "content_id": "BAD-ID",
        "package": "http://host/app/data/pkg/update/UP0000-CUSA22222_00-ABCDEFGHIJKLMNOP.pkg",
    }

    assert (
        pkg_redirect_path(entry)
        == "/pkg/update/UP0000-CUSA22222_00-ABCDEFGHIJKLMNOP.pkg"
    )


def test_given_valid_row_when_pkg_internal_path_then_returns_internal_alias_path():
    entry = {
        "apptype": "DLC",
        "content_id": "UP0000-CUSA99999_00-ABCDEFGHIJKLMNOP",
    }

    assert (
        pkg_internal_path(entry)
        == "/_internal_pkg/dlc/UP0000-CUSA99999_00-ABCDEFGHIJKLMNOP.pkg"
    )


def test_given_client_patch_label_when_pkg_redirect_then_maps_to_update_path():
    entry = {
        "apptype": "Patch",
        "content_id": "UP0000-CUSA00010_00-ABCDEFGHIJKLMNOP",
    }

    assert (
        pkg_redirect_path(entry)
        == "/pkg/update/UP0000-CUSA00010_00-ABCDEFGHIJKLMNOP.pkg"
    )


def test_given_content_id_when_increment_downloads_then_persists_value(tmp_path):
    db_path = tmp_path / "store.db"
    _create_homebrews_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO homebrews (id, content_id, apptype, package, number_of_downloads)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "CUSA00077",
            "UP0000-CUSA00077_00-ABCDEFGHIJKLMNOP",
            "game",
            "http://host/pkg/game/UP0000-CUSA00077_00-ABCDEFGHIJKLMNOP.pkg",
            3,
        ),
    )
    conn.commit()
    conn.close()

    updated = increment_downloads_by_content_id(
        "UP0000-CUSA00077_00-ABCDEFGHIJKLMNOP", db_path
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT number_of_downloads FROM homebrews WHERE content_id = ?",
        ("UP0000-CUSA00077_00-ABCDEFGHIJKLMNOP",),
    ).fetchone()
    conn.close()

    assert updated == 4
    assert row is not None
    assert row[0] == 4


def test_given_unknown_content_id_when_increment_downloads_then_returns_none(tmp_path):
    db_path = tmp_path / "store.db"
    _create_homebrews_db(db_path)

    updated = increment_downloads_by_content_id(
        "UP0000-CUSA99999_00-ABCDEFGHIJKLMNOP", db_path
    )

    assert updated is None


def test_given_pkg_url_when_pkg_file_path_then_returns_sanitized_disk_path(
    temp_globals,
):
    entry = {
        "apptype": "unknown",
        "content_id": "BAD-CONTENT-ID",
        "package": "https://host/pkg/game/UP0000-CUSA12345_00-ABCDEFGHIJKLMNOP.pkg",
    }

    path = pkg_file_path(entry)

    assert (
        path
        == temp_globals.PKG_DIR_PATH
        / "game"
        / "UP0000-CUSA12345_00-ABCDEFGHIJKLMNOP.pkg"
    )
