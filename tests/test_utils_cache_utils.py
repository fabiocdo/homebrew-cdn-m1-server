from hb_store_m1.models.output import Status
from hb_store_m1.utils.cache_utils import CacheUtils


def test_given_missing_cache_when_read_pkg_cache_then_returns_not_found(
    temp_globals,
):
    result = CacheUtils.read_pkg_cache()

    assert result.status is Status.NOT_FOUND
    assert result.content == {}


def test_given_invalid_cache_when_read_pkg_cache_then_returns_error(
    temp_globals,
):
    cache_path = temp_globals.CACHE_DIR_PATH / "store-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not-json}", encoding="utf-8")

    result = CacheUtils.read_pkg_cache()

    assert result.status is Status.ERROR


def test_given_pkg_dir_missing_when_write_pkg_cache_then_returns_not_found(
    temp_globals,
):
    result = CacheUtils.write_pkg_cache()

    assert result.status is Status.NOT_FOUND


def test_given_pkg_changes_when_compare_pkg_cache_then_reports_added(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")

    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.read_content_id",
        lambda path: path.stem.upper(),
    )

    CacheUtils.write_pkg_cache()

    extra_pkg = init_paths.DLC_DIR_PATH / "dlc.pkg"
    extra_pkg.write_text("data", encoding="utf-8")

    result = CacheUtils.compare_pkg_cache()
    changes = result.content

    assert result.status is Status.OK
    assert "dlc" in changes["changed"]
    assert changes["added"]["dlc"] == ["DLC"]


def test_given_media_without_pkg_when_write_pkg_cache_then_excludes_media(
    init_paths, monkeypatch
):
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.read_content_id",
        lambda path: path.stem.upper(),
    )
    media_path = init_paths.MEDIA_DIR_PATH / "ORPHAN_icon0.png"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"png")

    result = CacheUtils.write_pkg_cache()
    cache = result.content or {}
    media_section = cache.get("_media")

    assert result.status is Status.OK
    assert media_section is not None
    assert "ORPHAN_icon0" not in media_section.content


def test_given_media_with_pkg_when_write_pkg_cache_then_includes_media(
    init_paths, monkeypatch
):
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.read_content_id",
        lambda path: path.stem.upper(),
    )
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")
    media_path = init_paths.MEDIA_DIR_PATH / "GAME_icon0.png"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"png")

    result = CacheUtils.write_pkg_cache()
    cache = result.content or {}
    media_section = cache.get("_media")

    assert result.status is Status.OK
    assert media_section is not None
    assert "GAME_icon0" in media_section.content
