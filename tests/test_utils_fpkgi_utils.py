import json
from urllib.parse import urljoin

from hb_store_m1.models.fpkgi import FPKGI
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.utils.fpkgi_utils import FPKGIUtils


def _read_data(path):
    payload = json.loads(path.read_text("utf-8"))
    return payload[FPKGI.Root.DATA.value]


def test_given_app_type_when_json_path_requested_then_uses_uppercase_pattern(init_paths):
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


def test_given_pkg_without_content_id_when_upsert_then_ignores_or_uses_fallback(init_paths):
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


def test_given_legacy_json_list_and_lowercase_file_when_refresh_then_migrates(init_paths):
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
