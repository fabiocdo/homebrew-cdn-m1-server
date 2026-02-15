import json
import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from hb_store_m1.models.fpkgi import FPKGI
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.utils.fpkgi_utils import FPKGIUtils


def _read_data(path):
    payload = json.loads(path.read_text("utf-8"))
    return payload[FPKGI.Root.DATA.value]


def test_given_app_type_when_json_path_requested_then_uses_uppercase_pattern(
    init_paths,
):
    assert FPKGIUtils.json_path_for_app_type("game").name == "GAMES.json"
    assert FPKGIUtils.json_path_for_app_type("dlc").name == "DLC.json"
    assert FPKGIUtils.json_path_for_app_type("update").name == "UPDATES.json"


def test_given_pkg_when_upsert_then_writes_data_dict_per_app_type(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    icon_path = init_paths.MEDIA_DIR_PATH / "game_icon0.png"
    icon_path.write_text("png", encoding="utf-8")

    dlc_path = init_paths.DLC_DIR_PATH / "dlc.pkg"
    dlc_path.write_text("data", encoding="utf-8")
    dlc_icon = init_paths.MEDIA_DIR_PATH / "dlc_icon0.png"
    dlc_icon.write_text("png", encoding="utf-8")

    game_pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        icon0_png_path=icon_path,
        pkg_path=pkg_path,
    )
    dlc_pkg = PKG(
        title="DLC Title",
        title_id="CUSA00002",
        content_id="UP0000-TEST00000_00-DLC0000000000000",
        category="AC",
        version="01.00",
        icon0_png_path=dlc_icon,
        pkg_path=dlc_path,
    )

    result = FPKGIUtils.upsert([game_pkg, dlc_pkg])

    game_path = FPKGIUtils.json_path_for_app_type("game")
    dlc_json_path = FPKGIUtils.json_path_for_app_type("dlc")

    assert result.status is Status.OK
    assert game_path.exists()
    assert dlc_json_path.exists()

    game_data = _read_data(game_path)
    dlc_data = _read_data(dlc_json_path)

    expected_game_url = urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )
    expected_game_cover = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
    )
    expected_dlc_url = urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/dlc/UP0000-TEST00000_00-DLC0000000000000.pkg"
    )

    game_entry = game_data[expected_game_url]
    assert game_entry[FPKGI.Column.TITLE_ID.value] == "CUSA00001"
    assert game_entry[FPKGI.Column.REGION.value] == "USA"
    assert game_entry[FPKGI.Column.NAME.value] == "Game Title"
    assert game_entry[FPKGI.Column.VERSION.value] == "01.00"
    assert game_entry[FPKGI.Column.RELEASE.value] is None
    assert game_entry[FPKGI.Column.SIZE.value] == pkg_path.stat().st_size
    assert game_entry[FPKGI.Column.MIN_FW.value] is None
    assert game_entry[FPKGI.Column.COVER_URL.value] == expected_game_cover

    assert expected_dlc_url in dlc_data
    assert dlc_data[expected_dlc_url][FPKGI.Column.NAME.value] == "DLC Title"


def test_given_pkg_with_system_ver_when_upsert_then_writes_min_fw(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")

    pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        system_ver="0x05050000",
        pkg_path=pkg_path,
    )

    result = FPKGIUtils.upsert([pkg])
    game_data = _read_data(FPKGIUtils.json_path_for_app_type("game"))
    entry = next(iter(game_data.values()))

    assert result.status is Status.OK
    assert entry[FPKGI.Column.MIN_FW.value] == "5.05"


def test_given_unchanged_pkg_when_upsert_then_skips(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    icon_path = init_paths.MEDIA_DIR_PATH / "game_icon0.png"
    icon_path.write_text("png", encoding="utf-8")

    pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        icon0_png_path=icon_path,
        pkg_path=pkg_path,
    )

    first = FPKGIUtils.upsert([pkg])
    second = FPKGIUtils.upsert([pkg])

    assert first.status is Status.OK
    assert second.status is Status.SKIP


def test_given_content_ids_when_delete_then_removes_entries(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")

    pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )

    FPKGIUtils.upsert([pkg])
    delete_result = FPKGIUtils.delete_by_content_ids([pkg.content_id])
    game_data = _read_data(FPKGIUtils.json_path_for_app_type("game"))

    assert delete_result.status is Status.OK
    assert not game_data


def test_given_no_pkgs_when_upsert_then_returns_skip():
    result = FPKGIUtils.upsert([])
    assert result.status is Status.SKIP


def test_given_invalid_json_when_upsert_then_returns_error(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )
    FPKGIUtils.json_path_for_app_type("game").write_text("{bad", encoding="utf-8")

    result = FPKGIUtils.upsert([pkg])
    assert result.status is Status.ERROR


def test_given_invalid_json_when_delete_then_returns_error(init_paths):
    FPKGIUtils.json_path_for_app_type("game").write_text("{bad", encoding="utf-8")
    result = FPKGIUtils.delete_by_content_ids(["UP0000-TEST00000_00-TEST000000000000"])
    assert result.status is Status.ERROR


def test_given_pkg_without_path_when_upsert_then_size_is_zero(init_paths):
    pkg = PKG(
        title="Game Title",
        title_id="CUSA00001",
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        version="01.00",
        pkg_path=None,
    )

    result = FPKGIUtils.upsert([pkg])
    game_data = _read_data(FPKGIUtils.json_path_for_app_type("game"))
    entry = next(iter(game_data.values()))

    assert result.status is Status.OK
    assert entry[FPKGI.Column.SIZE.value] == 0


def test_given_empty_ids_when_delete_then_returns_skip():
    result = FPKGIUtils.delete_by_content_ids([])
    assert result.status is Status.SKIP


def test_given_existing_entry_when_upsert_then_replaces_in_place(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    package_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")
    path = FPKGIUtils.json_path_for_app_type("game")
    path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    package_url: {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "Old",
                        FPKGI.Column.VERSION.value: "00.01",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="New",
        title_id="CUSA00001",
        content_id=content_id,
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )

    result = FPKGIUtils.upsert([pkg])
    data = _read_data(path)

    assert result.status is Status.OK
    assert len(data) == 1
    assert data[package_url][FPKGI.Column.NAME.value] == "New"


def test_given_pkg_without_content_id_when_upsert_then_ignores_or_uses_fallback(
    init_paths,
):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    pkg = PKG(
        title="No ID",
        title_id="CUSA00001",
        content_id="",
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )

    result = FPKGIUtils.upsert([pkg])
    assert result.status in (Status.OK, Status.SKIP)


def test_given_old_json_urls_when_refresh_then_rewrites_base_and_pkg_path(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    old_server = "http://10.0.0.10:8080"
    old_pkg_url = f"{old_server}/app/data/pkg/game/{content_id}.pkg"
    path = FPKGIUtils.json_path_for_app_type("game")
    path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    old_pkg_url: {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "Old",
                        FPKGI.Column.VERSION.value: "00.01",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: f"{old_server}/app/data/pkg/_media/{content_id}_icon0.png",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.refresh_urls()
    data = _read_data(path)
    expected_pkg_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")

    assert result.status is Status.OK
    assert expected_pkg_url in data
    assert data[expected_pkg_url][FPKGI.Column.COVER_URL.value] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_icon0.png"
    )


def test_given_external_cover_url_when_refresh_then_keeps_external_cover(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    package_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")
    external_cover = "https://cdn.example.org/covers/game.png"
    path = FPKGIUtils.json_path_for_app_type("game")
    path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    package_url: {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "Old",
                        FPKGI.Column.VERSION.value: "00.01",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: external_cover,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.refresh_urls()
    data = _read_data(path)

    assert result.status is Status.SKIP
    assert data[package_url][FPKGI.Column.COVER_URL.value] == external_cover


def test_given_legacy_json_list_and_lowercase_file_when_refresh_then_migrates(
    init_paths,
):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    legacy_path = Globals.PATHS.DATA_DIR_PATH / "game.json"
    legacy_path.write_text(
        json.dumps(
            [
                {
                    FPKGI.LegacyColumn.ID.value: content_id,
                    FPKGI.LegacyColumn.NAME.value: "Legacy",
                    FPKGI.LegacyColumn.VERSION.value: "01.00",
                    FPKGI.LegacyColumn.PACKAGE.value: f"http://old.host/app/data/pkg/game/{content_id}.pkg",
                    FPKGI.LegacyColumn.SIZE.value: 10,
                    FPKGI.LegacyColumn.ICON.value: f"http://old.host/app/data/pkg/_media/{content_id}_icon0.png",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.refresh_urls()
    migrated_path = FPKGIUtils.json_path_for_app_type("game")
    data = _read_data(migrated_path)
    expected_pkg_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")

    assert result.status is Status.OK
    assert migrated_path.exists()
    assert not legacy_path.exists()
    assert expected_pkg_url in data
    assert data[expected_pkg_url][FPKGI.Column.NAME.value] == "Legacy"


def test_given_helper_inputs_when_normalizing_then_handles_edge_cases(init_paths):
    assert FPKGIUtils._to_int("abc", 7) == 7
    assert FPKGIUtils._normalize_region("") is None
    assert FPKGIUtils._normalize_region("br") is None
    assert FPKGIUtils._normalize_release("2026-02-14") == "02-14-2026"
    assert FPKGIUtils._normalize_release("14/02/2026") == "14/02/2026"
    assert FPKGIUtils._normalize_min_fw("0x05050000") == "5.05"
    assert FPKGIUtils._normalize_min_fw("050A0000") == "5.10"
    assert FPKGIUtils._normalize_min_fw("9.00") == "9.00"
    assert FPKGIUtils._normalize_min_fw("abc") == "abc"

    assert FPKGIUtils._content_id_from_pkg_url("") is None
    assert FPKGIUtils._content_id_from_pkg_url("https://x/y/file.txt") is None
    assert FPKGIUtils._region_from_content_id("U") is None

    assert FPKGIUtils._rewrite_public_url(None) is None
    assert FPKGIUtils._rewrite_public_url("http://legacy-host") is None
    assert (
        FPKGIUtils._rewrite_public_url("legacy/path/without/pkg-marker")
        == "legacy/path/without/pkg-marker"
    )


def test_given_legacy_file_when_cleanup_fails_then_logs_warning(
    init_paths, monkeypatch
):
    json_path = FPKGIUtils.json_path_for_app_type("game")
    legacy_path = Globals.PATHS.DATA_DIR_PATH / "game.json"
    legacy_path.write_text("[]", encoding="utf-8")

    original_unlink = Path.unlink

    def fake_unlink(path_obj, *args, **kwargs):
        if path_obj == legacy_path:
            raise OSError("nope")
        return original_unlink(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)

    assert legacy_path.exists()


def test_given_read_json_edge_cases_when_parsing_then_handles_variants(init_paths):
    path = FPKGIUtils.json_path_for_app_type("game")

    data, migrated = FPKGIUtils._read_json(path, "game")
    assert data == {}
    assert migrated is False

    path.write_text(json.dumps({FPKGI.Root.DATA.value: []}), encoding="utf-8")
    data, migrated = FPKGIUtils._read_json(path, "game")
    assert data is None
    assert migrated is False

    path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    "": {},
                    "http://x/not-dict.pkg": "bad",
                    "http://x/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg": {
                        FPKGI.Column.NAME.value: "X",
                        FPKGI.Column.SIZE.value: "10",
                        FPKGI.Column.REGION.value: "usa",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    data, migrated = FPKGIUtils._read_json(path, "game")
    assert migrated is False
    assert len(data) == 1
    entry = next(iter(data.values()))
    assert entry[FPKGI.Column.SIZE.value] == 10
    assert entry[FPKGI.Column.REGION.value] == "USA"

    path.write_text(
        json.dumps(
            {
                "http://x/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg": {
                    FPKGI.Column.NAME.value: "Y"
                }
            }
        ),
        encoding="utf-8",
    )
    data, migrated = FPKGIUtils._read_json(path, "game")
    assert migrated is True
    assert len(data) == 1

    path.write_text(json.dumps({"bad": []}), encoding="utf-8")
    data, migrated = FPKGIUtils._read_json(path, "game")
    assert data is None
    assert migrated is False


def test_given_upsert_with_invalid_and_stale_entries_when_run_then_keeps_only_canonical(
    init_paths,
):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    legacy_path = Globals.PATHS.DATA_DIR_PATH / "game.json"
    legacy_path.write_text(
        json.dumps(
            [
                {
                    FPKGI.LegacyColumn.ID.value: content_id,
                    FPKGI.LegacyColumn.NAME.value: "Legacy",
                    FPKGI.LegacyColumn.VERSION.value: "01.00",
                    FPKGI.LegacyColumn.PACKAGE.value: f"http://old.host/app/data/pkg/game/{content_id}.pkg",
                    FPKGI.LegacyColumn.SIZE.value: 10,
                    FPKGI.LegacyColumn.ICON.value: f"http://old.host/app/data/pkg/_media/{content_id}_icon0.png",
                }
            ]
        ),
        encoding="utf-8",
    )

    invalid_pkg = PKG(
        title="Invalid",
        title_id="CUSA00000",
        content_id="",
        category="GD",
        version="01.00",
        pkg_path=None,
    )
    pkg_path = init_paths.GAME_DIR_PATH / "good.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    valid_pkg = PKG(
        title="Good",
        title_id="CUSA00001",
        content_id=content_id,
        category="GD",
        version="01.00",
        pkg_path=pkg_path,
    )

    result = FPKGIUtils.upsert([invalid_pkg, valid_pkg])
    assert result.status is Status.OK
    assert not legacy_path.exists()

    game_path = FPKGIUtils.json_path_for_app_type("game")
    game_path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    f"http://old.host/pkg/game/{content_id}.pkg": {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "Old Host",
                        FPKGI.Column.VERSION.value: "01.00",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.upsert([valid_pkg])
    data = _read_data(game_path)
    canonical_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")

    assert result.status is Status.OK
    assert list(data.keys()) == [canonical_url]


def test_given_delete_and_refresh_edge_branches_when_run_then_handles_migrations(
    init_paths,
):
    legacy_save_path = Globals.PATHS.DATA_DIR_PATH / "save.json"
    legacy_save_path.write_text("[]", encoding="utf-8")

    delete_result = FPKGIUtils.delete_by_content_ids(
        ["UP0000-TEST00000_00-TEST000000000000"]
    )
    assert delete_result.status is Status.OK
    assert FPKGIUtils.json_path_for_app_type("save").exists()
    assert not legacy_save_path.exists()

    game_path = FPKGIUtils.json_path_for_app_type("game")
    game_path.write_text("{bad", encoding="utf-8")
    refresh_error = FPKGIUtils.refresh_urls()
    assert refresh_error.status is Status.ERROR

    game_path.unlink()
    legacy_game_path = Globals.PATHS.DATA_DIR_PATH / "game.json"
    legacy_game_path.write_text("[]", encoding="utf-8")
    refresh_ok = FPKGIUtils.refresh_urls()
    assert refresh_ok.status is Status.OK
    assert FPKGIUtils.json_path_for_app_type("game").exists()
    assert not legacy_game_path.exists()


def test_given_refresh_with_duplicate_canonical_url_when_run_then_marks_changed(
    init_paths,
):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    canonical_url = urljoin(Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg")
    game_path = FPKGIUtils.json_path_for_app_type("game")
    game_path.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    "http://legacy-host": {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "usa",
                        FPKGI.Column.NAME.value: "Legacy Host",
                        FPKGI.Column.VERSION.value: "01.00",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: "1",
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    },
                    f"http://old.host/pkg/game/{content_id}.pkg": {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "A",
                        FPKGI.Column.VERSION.value: "01.00",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    },
                    canonical_url: {
                        FPKGI.Column.TITLE_ID.value: "CUSA00001",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "B",
                        FPKGI.Column.VERSION.value: "01.00",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.refresh_urls()
    data = _read_data(game_path)

    assert result.status is Status.OK
    assert canonical_url in data


def test_given_store_db_rows_when_bootstrap_then_builds_fpkgi_json_fast(init_paths):
    db_path = Globals.FILES.STORE_DB_FILE_PATH
    init_sql_path = Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    init_sql = init_sql_path.read_text("utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(init_sql)
        conn.execute(
            """
            INSERT INTO homebrews
            (content_id, id, name, image, package, version, Size, apptype, releaseddate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "UP0000-TEST00000_00-TEST000000000000",
                "CUSA00001",
                "Game",
                "http://old.host/app/data/pkg/_media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
                "http://old.host/app/data/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg",
                "01.23",
                123,
                "Game",
                "2026-02-14",
            ),
        )
        conn.execute(
            """
            INSERT INTO homebrews
            (content_id, id, name, image, package, version, Size, apptype, releaseddate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "UP0000-TEST00000_00-UPD0000000000000",
                "CUSA00001",
                "Patch",
                "http://old.host/app/data/pkg/_media/UP0000-TEST00000_00-UPD0000000000000_icon0.png",
                "http://old.host/app/data/pkg/update/UP0000-TEST00000_00-UPD0000000000000.pkg",
                "01.24",
                321,
                "Patch",
                "2026-02-15",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    result = FPKGIUtils.bootstrap_from_store_db(["game", "update"])
    game_data = _read_data(FPKGIUtils.json_path_for_app_type("game"))
    update_data = _read_data(FPKGIUtils.json_path_for_app_type("update"))

    game_url = urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )
    update_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/update/UP0000-TEST00000_00-UPD0000000000000.pkg",
    )

    assert result.status is Status.OK
    assert game_data[game_url][FPKGI.Column.NAME.value] == "Game"
    assert game_data[game_url][FPKGI.Column.RELEASE.value] == "02-14-2026"
    assert update_data[update_url][FPKGI.Column.NAME.value] == "Patch"


def test_given_missing_store_db_when_bootstrap_then_returns_not_found(init_paths):
    result = FPKGIUtils.bootstrap_from_store_db(["game"])
    assert result.status is Status.NOT_FOUND


def test_given_stale_dlc_json_when_sync_from_db_then_clears_stale_entries(init_paths):
    db_path = Globals.FILES.STORE_DB_FILE_PATH
    init_sql_path = Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    init_sql = init_sql_path.read_text("utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(init_sql)
        conn.execute(
            """
            INSERT INTO homebrews
            (content_id, id, name, image, package, version, Size, apptype, releaseddate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "UP0000-TEST00000_00-TEST000000000000",
                "CUSA00001",
                "Game",
                "http://old.host/app/data/pkg/_media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
                "http://old.host/app/data/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg",
                "01.23",
                123,
                "Game",
                "2026-02-14",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    dlc_json = FPKGIUtils.json_path_for_app_type("dlc")
    stale_dlc_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/dlc/UP0000-TEST00000_00-DLC0000000000000.pkg",
    )
    dlc_json.write_text(
        json.dumps(
            {
                FPKGI.Root.DATA.value: {
                    stale_dlc_url: {
                        FPKGI.Column.TITLE_ID.value: "CUSA99999",
                        FPKGI.Column.REGION.value: "USA",
                        FPKGI.Column.NAME.value: "Stale DLC",
                        FPKGI.Column.VERSION.value: "01.00",
                        FPKGI.Column.RELEASE.value: None,
                        FPKGI.Column.SIZE.value: 1,
                        FPKGI.Column.MIN_FW.value: None,
                        FPKGI.Column.COVER_URL.value: None,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.sync_from_store_db()
    dlc_data = _read_data(dlc_json)

    assert result.status is Status.OK
    assert dlc_data == {}
