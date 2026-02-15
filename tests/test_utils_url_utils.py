from pathlib import Path
from urllib.parse import urljoin

from hb_store_m1.models.globals import Globals
from hb_store_m1.utils.url_utils import URLUtils


def test_given_app_data_path_when_normalize_then_returns_pkg_path():
    value = "/app/data/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg"

    normalized = URLUtils.normalize_public_path(value)

    assert normalized == "/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg"


def test_given_url_without_path_when_normalize_then_returns_none():
    assert URLUtils.normalize_public_path("https://example.com") is None


def test_given_absolute_path_under_pkg_root_when_normalize_then_relativizes(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    normalized = URLUtils.normalize_public_path(str(pkg_path))

    assert normalized == "/pkg/game/sample.pkg"


def test_given_pkg_root_path_when_normalize_then_returns_pkg_root(init_paths):
    normalized = URLUtils.normalize_public_path(str(init_paths.PKG_DIR_PATH))

    assert normalized == "/pkg"


def test_given_relative_path_when_normalize_then_prefixes_slash():
    normalized = URLUtils.normalize_public_path("pkg/game/file.pkg")

    assert normalized == "/pkg/game/file.pkg"


def test_given_path_resolve_error_when_normalize_then_falls_back(monkeypatch):
    original_resolve = Path.resolve

    def raise_error(self, *args, **kwargs):
        raise OSError("resolve failed")

    monkeypatch.setattr(Path, "resolve", raise_error)
    try:
        normalized = URLUtils.normalize_public_path("game/file.pkg")
    finally:
        monkeypatch.setattr(Path, "resolve", original_resolve)

    assert normalized == "/game/file.pkg"


def test_given_valid_content_id_when_canonical_pkg_url_then_uses_content_id():
    value = URLUtils.canonical_pkg_url(
        "UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP", "game", "/tmp/random.pkg"
    )

    assert value == urljoin(
        Globals.ENVS.SERVER_URL, "/pkg/game/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP.pkg"
    )


def test_given_invalid_content_id_when_canonical_media_url_then_uses_fallback():
    value = URLUtils.canonical_media_url(
        "BAD", "icon0", "/app/data/pkg/_media/raw_icon0.png"
    )

    assert value == urljoin(Globals.ENVS.SERVER_URL, "/pkg/_media/raw_icon0.png")


def test_given_client_label_when_normalize_app_type_section_then_maps_to_pkg_section():
    assert URLUtils.normalize_app_type_section("Patch") == "update"
    assert URLUtils.normalize_app_type_section("DLC") == "dlc"
    assert URLUtils.normalize_app_type_section("Game") == "game"


def test_given_internal_app_type_when_to_client_app_type_then_returns_ps4_store_label():
    assert URLUtils.to_client_app_type("game") == "Game"
    assert URLUtils.to_client_app_type("update") == "Patch"
    assert URLUtils.to_client_app_type("save") == "Other"


def test_given_valid_content_id_when_ps4_store_icon_cache_path_then_returns_local_path():
    value = URLUtils.ps4_store_icon_cache_path("UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP")

    assert (
        value
        == "/user/app/NPXS39041/storedata/UP0000-CUSA00001_00-ABCDEFGHIJKLMNOP_icon0.png"
    )


def test_given_non_standard_content_id_when_ps4_store_icon_cache_path_then_still_returns_local_path():
    value = URLUtils.ps4_store_icon_cache_path("UP9000-CUSA01967_00-POBANUKTRAVPACK0")

    assert (
        value
        == "/user/app/NPXS39041/storedata/UP9000-CUSA01967_00-POBANUKTRAVPACK0_icon0.png"
    )
