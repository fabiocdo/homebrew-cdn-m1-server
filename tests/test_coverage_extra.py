import sqlite3
from pathlib import Path

import pytest
from github import GithubException

from hb_store_m1.models import globals as globals_module
from hb_store_m1.models.cache import CacheSection
from hb_store_m1.models.globals import _env, _pyproject_value
from hb_store_m1.models.output import Status, Output
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFO, ParamSFOKey
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntry, PKGEntryKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.section import SectionEntry
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


def test_given_unsupported_env_type_when_parse_then_raises_type_error(monkeypatch):
    monkeypatch.setenv("TEST_LIST", "a, b")
    with pytest.raises(TypeError):
        _env("TEST_LIST", [], list)


def test_given_pyproject_missing_when_read_then_returns_default(tmp_path):
    missing = tmp_path / "missing.toml"
    assert _pyproject_value(missing, "name", "default") == "default"


def test_given_pyproject_present_when_read_then_returns_value(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert _pyproject_value(pyproject, "name", "default") == "demo"


def test_given_missing_pyproject_path_when_parent_has_file_then_reads_value(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\nversion='1.2.3'\n", encoding="utf-8"
    )
    monkeypatch.chdir(nested)

    assert _pyproject_value(nested / "pyproject.toml", "version", "default") == "1.2.3"


def test_given_pyproject_missing_when_app_version_then_uses_installed_metadata(
    monkeypatch,
):
    monkeypatch.setattr(
        globals_module, "_pyproject_value", lambda *_args, **_kwargs: ""
    )
    monkeypatch.setattr(globals_module._metadata, "version", lambda _name: "9.9.9")

    envs = globals_module._GlobalEnvs(globals_module.Globals.FILES)

    assert envs.APP_VERSION == "9.9.9"


def test_given_pyproject_missing_when_app_name_then_uses_installed_metadata(
    monkeypatch,
):
    monkeypatch.setattr(
        globals_module, "_pyproject_value", lambda *_args, **_kwargs: ""
    )
    monkeypatch.setattr(
        globals_module._metadata,
        "metadata",
        lambda _name: {"Name": "hb-store-m1-meta"},
    )

    envs = globals_module._GlobalEnvs(globals_module.Globals.FILES)

    assert envs.APP_NAME == "hb-store-m1-meta"


def test_given_no_pyproject_and_no_metadata_when_app_version_then_falls_back_default(
    monkeypatch,
):
    monkeypatch.setattr(
        globals_module, "_pyproject_value", lambda *_args, **_kwargs: ""
    )

    def _raise_not_found(_name):
        raise globals_module._metadata.PackageNotFoundError

    monkeypatch.setattr(globals_module._metadata, "version", _raise_not_found)

    envs = globals_module._GlobalEnvs(globals_module.Globals.FILES)

    assert envs.APP_VERSION == "0.0.1"


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
    pkg = PKG(content_id="", category="GD", pkg_path=pkg_path)
    result = AutoOrganizer.dry_run(pkg)
    assert result.status is Status.INVALID


def test_given_conflict_when_dry_run_then_returns_conflict(init_paths):
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    target = init_paths.GAME_DIR_PATH / f"{content_id}.pkg"
    target.write_text("pkg", encoding="utf-8")
    source = init_paths.PKG_DIR_PATH / "raw.pkg"
    source.write_text("pkg", encoding="utf-8")
    pkg = PKG(content_id=content_id, category="GD", pkg_path=source)
    result = AutoOrganizer.dry_run(pkg)

    assert result.status is Status.CONFLICT


def test_given_move_failure_when_run_then_returns_none(init_paths, monkeypatch):
    pkg_path = init_paths.PKG_DIR_PATH / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pkg_path=pkg_path,
    )

    monkeypatch.setattr(file_utils_module.FileUtils, "move", lambda *_: None)
    result = AutoOrganizer.run(pkg)

    assert result is None


def test_given_no_changes_when_run_cycle_then_skips_scan(init_paths, monkeypatch):
    watcher = Watcher()
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    called = {"write": False}
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "write_pkg_cache",
        lambda *args, **kwargs: called.__setitem__("write", True),
    )

    watcher._run_cycle()

    assert called["write"] is False


def test_given_fpkgi_enabled_and_missing_json_when_run_cycle_then_runs(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    cache = {
        "game": CacheSection(
            content={"UP0000-TEST00000_00-TEST000000000000": "1|2|sample.pkg"}
        )
    }

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "read_pkg_cache",
        lambda: Output(Status.OK, cache),
    )
    monkeypatch.setattr(
        globals_module.Globals.ENVS, "FPGKI_FORMAT_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.validate",
        lambda _p: Output(Status.OK, _p),
    )
    sfo = ParamSFO(
        {
            ParamSFOKey.TITLE: "t",
            ParamSFOKey.TITLE_ID: "CUSA00001",
            ParamSFOKey.CONTENT_ID: "UP0000-TEST00000_00-TEST000000000000",
            ParamSFOKey.CATEGORY: "GD",
            ParamSFOKey.VERSION: "01.00",
            ParamSFOKey.PUBTOOLINFO: "",
        }
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.extract_pkg_data",
        lambda _p, **_kwargs: Output(Status.OK, sfo),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.extract_pkg_medias",
        lambda _p, _content_id: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.build_pkg",
        lambda _p, _sfo, _medias: Output(
            Status.OK, PKG(content_id="X", category="GD", pkg_path=_p)
        ),
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "upsert",
        lambda _pkgs: Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.upsert",
        lambda _pkgs: Output(Status.OK, 1),
    )
    called = {"write": False}
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "write_pkg_cache",
        lambda *args, **kwargs: called.__setitem__("write", True),
    )

    watcher._run_cycle()

    assert called["write"] is True


def test_given_upsert_error_when_run_cycle_then_skips_cache_write(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(
            Status.OK,
            {
                "changed": ["game"],
                "added": {"game": ["X"]},
                "updated": {},
                "removed": {},
                "current_files": {"game": {"X": "sample.pkg"}},
            },
        ),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.validate",
        lambda _p: Output(Status.OK, _p),
    )
    sfo = ParamSFO(
        {
            ParamSFOKey.TITLE: "t",
            ParamSFOKey.TITLE_ID: "CUSA00001",
            ParamSFOKey.CONTENT_ID: "X",
            ParamSFOKey.CATEGORY: "GD",
            ParamSFOKey.VERSION: "01.00",
            ParamSFOKey.PUBTOOLINFO: "",
        }
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.extract_pkg_data",
        lambda _p, **_kwargs: Output(Status.OK, sfo),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.build_pkg",
        lambda _p, _sfo, _medias: Output(
            Status.OK, PKG(content_id="X", category="GD", pkg_path=_p)
        ),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.pkg_utils.PkgUtils.extract_pkg_medias",
        lambda _p, _content_id: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "upsert",
        lambda _pkgs: Output(Status.ERROR, 1),
    )
    monkeypatch.setattr(
        "hb_store_m1.utils.fpkgi_utils.FPKGIUtils.upsert",
        lambda _pkgs: Output(Status.OK, 1),
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


def test_given_empty_content_ids_when_select_by_content_ids_then_returns_empty(
    temp_globals,
):
    conn = sqlite3.connect(":memory:")
    try:
        result = db_utils_module.DBUtils.select_by_content_ids(conn, [])
        assert result.status is Status.OK
        assert result.content == []
    finally:
        conn.close()


def test_given_upsert_exception_when_upsert_then_returns_error(init_paths, monkeypatch):
    init_sql = (
        Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    ).read_text("utf-8")
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    init_utils_module.InitUtils.init_db()

    class _BadConn:
        class _Cursor:
            def execute(self, *_args, **_kwargs):
                return None

            def fetchall(self):
                return []

        def cursor(self):
            return self._Cursor()

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
    assert file_utils_module.FileUtils.move(tmp_path / "missing.txt", target) is None


def test_given_invalid_png_when_optimize_then_returns_false(tmp_path):
    bad_png = tmp_path / "bad.png"
    bad_png.write_bytes(b"not-png")

    assert file_utils_module.FileUtils.optimize_png(bad_png) is False


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
