import json
from urllib.parse import urljoin

from hb_store_m1.models.fpkgi import FPKGI
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.utils.fpkgi_utils import FPKGIUtils


def test_given_app_type_when_json_path_requested_then_uses_uppercase_pattern(init_paths):
    assert FPKGIUtils.json_path_for_app_type("game").name == "GAMES.json"
    assert FPKGIUtils.json_path_for_app_type("dlc").name == "DLC.json"
    assert FPKGIUtils.json_path_for_app_type("update").name == "UPDATES.json"


def test_given_pkg_when_upsert_then_writes_json_per_app_type(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    icon_path = init_paths.MEDIA_DIR_PATH / "game_icon0.png"
    icon_path.write_text("png", encoding="utf-8")
    pic1_path = init_paths.MEDIA_DIR_PATH / "game_pic1.png"
    pic1_path.write_text("png", encoding="utf-8")

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
        pic1_png_path=pic1_path,
        pkg_path=pkg_path,
    )
    dlc_pkg = PKG(
        title="DLC Title",
        title_id="CUSA00002",
        content_id="UP0000-TEST00000_00-DLC000000000000",
        category="AC",
        version="01.00",
        icon0_png_path=dlc_icon,
        pkg_path=dlc_path,
    )

    result = FPKGIUtils.upsert([game_pkg, dlc_pkg])

    game_path = FPKGIUtils.json_path_for_app_type("game")
    dlc_path = FPKGIUtils.json_path_for_app_type("dlc")

    assert result.status is Status.OK
    assert game_path.exists()
    assert dlc_path.exists()

    game_data = json.loads(game_path.read_text("utf-8"))
    dlc_data = json.loads(dlc_path.read_text("utf-8"))

    game_entry = game_data[0]
    expected_pkg_url = urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )
    expected_icon_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
    )
    expected_pic1_url = urljoin(
        Globals.ENVS.SERVER_URL,
        "/pkg/_media/UP0000-TEST00000_00-TEST000000000000_pic1.png",
    )

    assert game_entry[FPKGI.Column.ID.value] == game_pkg.content_id
    assert game_entry[FPKGI.Column.PACKAGE.value] == expected_pkg_url
    assert game_entry[FPKGI.Column.ICON.value] == expected_icon_url
    assert game_entry[FPKGI.Column.BG_IMAGE.value] == expected_pic1_url
    assert game_entry[FPKGI.Column.SIZE.value] == pkg_path.stat().st_size

    dlc_entry = dlc_data[0]
    assert dlc_entry[FPKGI.Column.ID.value] == dlc_pkg.content_id


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

    game_data = json.loads(
        FPKGIUtils.json_path_for_app_type("game").read_text("utf-8")
    )

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
    game_data = json.loads(
        FPKGIUtils.json_path_for_app_type("game").read_text("utf-8")
    )

    assert result.status is Status.OK
    assert game_data[0][FPKGI.Column.SIZE.value] == 0


def test_given_empty_ids_when_delete_then_returns_skip():
    result = FPKGIUtils.delete_by_content_ids([])

    assert result.status is Status.SKIP


def test_given_existing_entry_when_upsert_then_replaces_in_place(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    path = FPKGIUtils.json_path_for_app_type("game")
    path.write_text(
        json.dumps(
            [
                {
                    FPKGI.Column.ID.value: content_id,
                    FPKGI.Column.NAME.value: "Old",
                    FPKGI.Column.VERSION.value: "00.01",
                    FPKGI.Column.PACKAGE.value: None,
                    FPKGI.Column.SIZE.value: 1,
                    FPKGI.Column.DESC.value: None,
                    FPKGI.Column.ICON.value: None,
                    FPKGI.Column.BG_IMAGE.value: None,
                }
            ]
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
    data = json.loads(path.read_text("utf-8"))

    assert result.status is Status.OK
    assert len(data) == 1
    assert data[0][FPKGI.Column.NAME.value] == "New"


def test_given_pkg_without_content_id_when_upsert_then_ignores_entry(init_paths):
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
    path = FPKGIUtils.json_path_for_app_type("game")
    path.write_text(
        json.dumps(
            [
                {
                    FPKGI.Column.ID.value: content_id,
                    FPKGI.Column.NAME.value: "Old",
                    FPKGI.Column.VERSION.value: "00.01",
                    FPKGI.Column.PACKAGE.value: f"{old_server}/app/data/pkg/game/{content_id}.pkg",
                    FPKGI.Column.SIZE.value: 1,
                    FPKGI.Column.DESC.value: None,
                    FPKGI.Column.ICON.value: f"{old_server}/app/data/pkg/_media/{content_id}_icon0.png",
                    FPKGI.Column.BG_IMAGE.value: f"{old_server}/app/data/pkg/_media/{content_id}_pic1.png",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = FPKGIUtils.refresh_urls()
    data = json.loads(path.read_text("utf-8"))
    entry = data[0]

    assert result.status is Status.OK
    assert entry[FPKGI.Column.PACKAGE.value] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/game/{content_id}.pkg"
    )
    assert entry[FPKGI.Column.ICON.value] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_icon0.png"
    )
    assert entry[FPKGI.Column.BG_IMAGE.value] == urljoin(
        Globals.ENVS.SERVER_URL, f"/pkg/_media/{content_id}_pic1.png"
    )
