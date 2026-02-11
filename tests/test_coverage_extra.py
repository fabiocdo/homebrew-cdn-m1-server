import sqlite3
from pathlib import Path

import pytest
from github import GithubException

from hb_store_m1.models import globals as globals_module
from hb_store_m1.models.globals import _env, _pyproject_value
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntry, PKGEntryKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.section import SectionEntry
from hb_store_m1.models.output import Status, Output
from hb_store_m1.modules.auto_organizer import AutoOrganizer
from hb_store_m1.modules.watcher import Watcher
from hb_store_m1.utils import cache_utils as cache_utils_module
from hb_store_m1.utils import db_utils as db_utils_module
from hb_store_m1.utils import file_utils as file_utils_module
from hb_store_m1.utils import init_utils as init_utils_module


def test_given_bool_env_when_parse_then_returns_bool(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "true")
    assert _env("TEST_BOOL", False, bool) is True
    monkeypatch.setenv("TEST_BOOL", "false")
    assert _env("TEST_BOOL", True, bool) is False


def test_given_invalid_bool_env_when_parse_then_raises(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "notbool")
    with pytest.raises(ValueError):
        _env("TEST_BOOL", False, bool)


def test_given_list_env_when_parse_then_uppercases(monkeypatch):
    monkeypatch.setenv("TEST_LIST", "a, b")
    assert _env("TEST_LIST", [], list) == ["A", "B"]


def test_given_pyproject_missing_when_read_then_returns_default(tmp_path):
    missing = tmp_path / "missing.toml"
    assert _pyproject_value(missing, "name", "default") == "default"


def test_given_pyproject_present_when_read_then_returns_value(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert _pyproject_value(pyproject, "name", "default") == "demo"


def test_given_pkg_entry_when_init_then_sets_fields():
    entry = PKGEntry(PKGEntryKey.PARAM_SFO, "1")
    assert entry.key is PKGEntryKey.PARAM_SFO
    assert entry.index == "1"


def test_given_pubtoolinfo_when_post_init_then_sets_release_date():
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pubtoolinfo="c_date=20240101",
    )
    assert pkg.release_date == "2024-01-01"


def test_given_media_section_when_accepts_then_allows_png(tmp_path):
    section = SectionEntry("_media", tmp_path)
    png_path = tmp_path / "example.png"
    png_path.write_bytes(b"png")
    assert section.accepts(png_path) is True


def test_given_invalid_content_id_when_dry_run_then_invalid(init_paths):
    pkg_path = init_paths.PKG_DIR_PATH / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    result = AutoOrganizer.dry_run(pkg_path, {"content_id": "bad/name"})
    assert result.status is Status.INVALID


def test_given_conflict_when_dry_run_then_returns_conflict(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    target = init_paths.GAME_DIR_PATH / f"{content_id}.pkg"
    target.write_text("pkg", encoding="utf-8")
    source = init_paths.PKG_DIR_PATH / "raw.pkg"
    source.write_text("pkg", encoding="utf-8")

    result = AutoOrganizer.dry_run(
        source, {"content_id": content_id, "app_type": "game"}
    )

    assert result.status is Status.CONFLICT


def test_given_move_failure_when_run_then_returns_none(init_paths, monkeypatch):
    pkg_path = init_paths.PKG_DIR_PATH / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(file_utils_module.FileUtils, "move", lambda *_: None)
    result = AutoOrganizer.run(
        pkg_path,
        {"content_id": "UP0000-TEST00000_00-TEST000000000000", "app_type": "game"},
    )

    assert result is None


def test_given_no_changes_when_run_cycle_then_skips_scan(
    init_paths, monkeypatch
):
    watcher = Watcher()
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.OK, {"changed": []}),
    )
    called = {"scan": False}
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.scan",
        lambda _s: called.__setitem__("scan", True),
    )

    watcher._run_cycle()

    assert called["scan"] is False


def test_given_upsert_error_when_run_cycle_then_skips_cache_write(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.OK, {"changed": ["game"]}),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.scan", lambda _s: [pkg_path]
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.validate",
        lambda _p: Output(Status.OK, _p),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.extract_pkg_data",
        lambda _p: Output(Status.OK, PKG(content_id="X", category="GD", pkg_path=_p)),
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "upsert",
        lambda _pkgs: Output(Status.ERROR, 1),
    )
    called = {"write": False}
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "write_pkg_cache",
        lambda: called.__setitem__("write", True),
    )

    watcher._run_cycle()

    assert called["write"] is False


def test_given_missing_cache_dir_when_write_then_handles_stat_error(
    init_paths, monkeypatch
):
    bad_pkg = init_paths.GAME_DIR_PATH / "bad.pkg"
    bad_pkg.write_text("pkg", encoding="utf-8")

    original_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        if self.name == "bad.pkg":
            raise OSError("stat failed")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    monkeypatch.setattr(
        "hb_store_m1.models.pkg.section.SectionEntry.accepts",
        lambda _self, _path: True,
    )

    result = cache_utils_module.CacheUtils.write_pkg_cache()

    assert result.status is Status.OK


def test_given_missing_db_when_generate_rows_md5_then_returns_empty(
    temp_globals,
):
    result = db_utils_module.DBUtils.generate_rows_md5()
    assert result == {}


def test_given_none_path_when_cdn_url_then_returns_none():
    assert db_utils_module.DBUtils._cdn_url(None) is None


def test_given_upsert_exception_when_upsert_then_returns_error(
    init_paths, monkeypatch
):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(
        init_sql, encoding="utf-8"
    )
    init_utils_module.InitUtils.init_db()

    class _BadConn:
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

    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: _BadConn())

    pkg = PKG(content_id="X", category="GD")
    result = db_utils_module.DBUtils.upsert([pkg])

    assert result.status is Status.ERROR


def test_given_missing_file_when_move_then_returns_none(tmp_path):
    target = tmp_path / "target.txt"
    assert file_utils_module.FileUtils.move(
        tmp_path / "missing.txt", target
    ) is None


def test_given_invalid_png_when_optimize_then_returns_false(tmp_path):
    bad_png = tmp_path / "bad.png"
    bad_png.write_bytes(b"not-png")

    assert (
        file_utils_module.FileUtils.optimize_png(bad_png) is False
    )


def test_given_missing_file_when_move_to_error_then_returns_none(tmp_path):
    errors_dir = tmp_path / "errors"
    assert (
        file_utils_module.FileUtils.move_to_error(
            tmp_path / "missing.pkg", errors_dir, "reason"
        )
        is None
    )


def test_given_missing_init_script_when_init_db_then_skips(init_paths):
    init_utils_module.InitUtils.init_db()
    assert not globals_module.Globals.FILES.STORE_DB_FILE_PATH.exists()


def test_given_empty_init_script_when_init_db_then_skips(init_paths):
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text("", encoding="utf-8")
    init_utils_module.InitUtils.init_db()
    assert not globals_module.Globals.FILES.STORE_DB_FILE_PATH.exists()


def test_given_invalid_template_json_when_init_template_json_then_skips(
    init_paths,
):
    template_path = init_paths.INIT_DIR_PATH / "json_template.json"
    template_path.write_text("{not-json}", encoding="utf-8")
    init_utils_module.InitUtils.init_template_json()
    assert not globals_module.Globals.FILES.INDEX_JSON_FILE_PATH.exists()


def test_given_github_exception_when_init_assets_then_handles_error(
    monkeypatch, temp_globals
):
    def fake_download(_assets):
        raise GithubException(400, {"message": "nope"}, None)

    monkeypatch.setattr(
        "hb_store_m1.utils.init_utils.StoreAssetClient.download_store_assets",
        fake_download,
    )

    init_utils_module.InitUtils.init_assets()
