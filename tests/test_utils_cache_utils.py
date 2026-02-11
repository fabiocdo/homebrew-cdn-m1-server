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
    init_paths,
):
    pkg_path = init_paths.GAME_DIR_PATH / "game.pkg"
    pkg_path.write_text("data", encoding="utf-8")

    CacheUtils.write_pkg_cache()

    extra_pkg = init_paths.DLC_DIR_PATH / "dlc.pkg"
    extra_pkg.write_text("data", encoding="utf-8")

    result = CacheUtils.compare_pkg_cache()
    changes = result.content

    assert result.status is Status.OK
    assert "dlc" in changes["changed"]
    assert changes["added"]["dlc"] == ["dlc.pkg"]
