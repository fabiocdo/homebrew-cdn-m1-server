import pytest

from hb_store_m1.models import globals as globals_module
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFO, ParamSFOKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.modules import auto_organizer as auto_organizer_module
from hb_store_m1.modules.watcher import Watcher
from hb_store_m1.utils import cache_utils as cache_utils_module
from hb_store_m1.utils import db_utils as db_utils_module
from hb_store_m1.utils import file_utils as file_utils_module
from hb_store_m1.utils import fpkgi_utils as fpkgi_utils_module
from hb_store_m1.utils import pkg_utils as pkg_utils_module


def test_given_media_change_when_pkgs_from_media_changes_then_returns_pkg_path(
    init_paths,
):
    watcher = Watcher()
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    pkg_path = init_paths.GAME_DIR_PATH / f"{content_id}.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    changes = {"removed": {"_media": [f"{content_id}_icon0.png"]}}

    pkgs = watcher._pkgs_from_media_changes(changes)

    assert pkgs == [pkg_path]


def test_given_changes_when_run_cycle_then_updates_cache(init_paths, monkeypatch):
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
                "added": {"game": ["UP0000-TEST00000_00-TEST000000000000"]},
                "updated": {},
                "removed": {},
                "current_files": {
                    "game": {"UP0000-TEST00000_00-TEST000000000000": "sample.pkg"}
                },
            },
        ),
    )
    monkeypatch.setattr(
        pkg_utils_module.PkgUtils,
        "validate",
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
        pkg_utils_module.PkgUtils,
        "extract_pkg_data",
        lambda _p, **_kwargs: Output(Status.OK, sfo),
    )
    monkeypatch.setattr(
        pkg_utils_module.PkgUtils,
        "extract_pkg_medias",
        lambda _p, _content_id: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        pkg_utils_module.PkgUtils,
        "build_pkg",
        lambda _p, _sfo, _medias: Output(
            Status.OK,
            PKG(
                title="t",
                title_id="CUSA00001",
                content_id="UP0000-TEST00000_00-TEST000000000000",
                category="GD",
                version="01.00",
                pkg_path=_p,
            ),
        ),
    )
    monkeypatch.setattr(
        auto_organizer_module.AutoOrganizer,
        "run",
        lambda _pkg: _pkg.pkg_path,
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "upsert",
        lambda _pkgs: Output(Status.OK, 1),
    )
    monkeypatch.setattr(
        fpkgi_utils_module.FPKGIUtils,
        "upsert",
        lambda _pkgs: Output(Status.OK, 1),
    )
    called = {}

    def fake_write():
        called["write"] = True
        return Output(Status.OK, {})

    monkeypatch.setattr(cache_utils_module.CacheUtils, "write_pkg_cache", fake_write)

    watcher._run_cycle()

    assert called.get("write") is True


def test_given_validation_error_when_run_cycle_then_moves_to_error(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "bad.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(
            Status.OK,
            {
                "changed": ["game"],
                "added": {"game": ["bad"]},
                "updated": {},
                "removed": {},
                "current_files": {"game": {"bad": "bad.pkg"}},
            },
        ),
    )
    monkeypatch.setattr(
        pkg_utils_module.PkgUtils,
        "validate",
        lambda _p: Output(Status.ERROR, _p),
    )
    moved = {}

    def fake_move(*_args, **_kwargs):
        moved["called"] = True
        return pkg_path

    monkeypatch.setattr(file_utils_module.FileUtils, "move_to_error", fake_move)

    watcher._run_cycle()

    assert moved.get("called") is True


def test_given_start_called_when_sleep_raises_then_cycle_runs_once(
    init_paths, monkeypatch
):
    watcher = Watcher()
    calls = []

    monkeypatch.setattr(watcher, "_run_cycle", lambda: calls.append("run"))
    monkeypatch.setattr(
        "hb_store_m1.modules.watcher.time.sleep",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("stop")),
    )

    with pytest.raises(RuntimeError):
        watcher.start()

    assert calls == ["run"]


def test_given_missing_cache_when_run_cycle_then_removes_db_orphans(
    init_paths, monkeypatch
):
    watcher = Watcher()

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "read_pkg_cache",
        lambda: Output(Status.NOT_FOUND, {}),
    )
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(
            Status.OK,
            {
                "changed": [],
                "added": {},
                "updated": {},
                "removed": {},
                "current_files": {"game": {"KEEP": "keep.pkg"}},
            },
        ),
    )
    monkeypatch.setattr(
        globals_module.Globals.ENVS, "FPGKI_FORMAT_ENABLED", False, raising=False
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "select_content_ids",
        lambda: Output(Status.OK, ["KEEP", "DROP"]),
    )
    deleted = {"ids": []}

    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "delete_by_content_ids",
        lambda ids: deleted.__setitem__("ids", ids) or Output(Status.OK, len(ids)),
    )
    monkeypatch.setattr(
        db_utils_module.DBUtils,
        "upsert",
        lambda _pkgs: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "write_pkg_cache",
        lambda *args, **kwargs: Output(Status.OK, {}),
    )

    watcher._run_cycle()

    assert deleted["ids"] == ["DROP"]


def test_given_media_without_suffix_when_content_id_from_media_then_returns_none():
    watcher = Watcher()

    assert watcher._content_id_from_media("plain.png") is None


def test_given_short_cache_entry_when_filename_from_cache_entry_then_falls_back():
    assert Watcher._filename_from_cache_entry("X", "1|2") == "X.pkg"


def test_given_missing_section_path_when_file_map_from_disk_then_returns_empty(
    tmp_path,
):
    section = type(
        "Section", (), {"path": tmp_path / "missing", "accepts": lambda *_: True}
    )()

    assert Watcher._file_map_from_disk(section) == {}


def test_given_scanned_changes_with_invalid_section_when_collect_scanned_pkgs_then_skips():
    watcher = Watcher()
    changes = type(
        "Changes",
        (),
        {
            "changed": ["_media", "invalid", "game"],
            "added": {"game": []},
            "updated": {"game": []},
            "removed": {},
            "current_files": {"game": {}},
        },
    )()

    scanned = watcher._collect_scanned_pkgs(changes)

    assert scanned == []


def test_given_canonical_pkg_name_when_check_then_returns_true(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "UP0000-CUSA00000_00-TEST000000000000.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    assert Watcher._is_canonical_pkg_filename(pkg_path) is True


def test_given_non_canonical_pkg_name_when_check_then_returns_false(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    assert Watcher._is_canonical_pkg_filename(pkg_path) is False


def test_given_process_pkg_failures_when_process_pkg_then_returns_none(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    moved_reasons = []

    monkeypatch.setattr(
        watcher._file_utils,
        "move_to_error",
        lambda _path, _errors_dir, reason: moved_reasons.append(reason) or _path,
    )

    monkeypatch.setattr(
        watcher._pkg_utils, "validate", lambda _p: Output(Status.OK, _p)
    )
    monkeypatch.setattr(
        watcher._pkg_utils, "extract_pkg_data", lambda _p: Output(Status.ERROR, None)
    )
    assert watcher._process_pkg(pkg_path) is None
    assert moved_reasons[-1] == "extract_data_failed"

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
        watcher._pkg_utils, "extract_pkg_data", lambda _p: Output(Status.OK, sfo)
    )
    monkeypatch.setattr(watcher._auto_organizer, "run", lambda _pkg: None)
    assert watcher._process_pkg(pkg_path) is None
    assert moved_reasons[-1] == "organizer_failed"

    monkeypatch.setattr(watcher._auto_organizer, "run", lambda _pkg: pkg_path)
    monkeypatch.setattr(
        watcher._pkg_utils,
        "extract_pkg_medias",
        lambda _p, _cid: Output(Status.ERROR, None),
    )
    assert watcher._process_pkg(pkg_path) is None
    assert moved_reasons[-1] == "extract_medias_failed"

    monkeypatch.setattr(
        watcher._pkg_utils,
        "extract_pkg_medias",
        lambda _p, _cid: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        watcher._pkg_utils, "build_pkg", lambda _p, _sfo, _m: Output(Status.ERROR, None)
    )
    assert watcher._process_pkg(pkg_path) is None
    assert moved_reasons[-1] == "build_failed"


def test_given_process_pkg_with_validation_warn_when_process_pkg_then_continues(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    moved = {"called": False}

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
    built_pkg = PKG(content_id="UP0000-TEST00000_00-TEST000000000000", category="GD")

    monkeypatch.setattr(
        watcher._pkg_utils, "validate", lambda _p: Output(Status.WARN, _p)
    )
    monkeypatch.setattr(
        watcher._pkg_utils, "extract_pkg_data", lambda _p: Output(Status.OK, sfo)
    )
    monkeypatch.setattr(watcher._auto_organizer, "run", lambda _pkg: pkg_path)
    monkeypatch.setattr(
        watcher._pkg_utils,
        "extract_pkg_medias",
        lambda _p, _cid: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        watcher._pkg_utils,
        "build_pkg",
        lambda _p, _sfo, _m: Output(Status.OK, built_pkg),
    )
    monkeypatch.setattr(
        watcher._file_utils,
        "move_to_error",
        lambda *_args, **_kwargs: moved.__setitem__("called", True),
    )

    result = watcher._process_pkg(pkg_path)

    assert result == built_pkg
    assert moved["called"] is False


def test_given_process_pkg_when_section_not_changed_then_still_runs_organizer(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    called = {"run": 0}

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
    built_pkg = PKG(content_id="UP0000-TEST00000_00-TEST000000000000", category="GD")

    monkeypatch.setattr(
        watcher._pkg_utils, "validate", lambda _p: Output(Status.OK, _p)
    )
    monkeypatch.setattr(
        watcher._pkg_utils, "extract_pkg_data", lambda _p: Output(Status.OK, sfo)
    )
    monkeypatch.setattr(
        watcher._auto_organizer,
        "run",
        lambda _pkg: called.__setitem__("run", called["run"] + 1) or pkg_path,
    )
    monkeypatch.setattr(
        watcher._pkg_utils,
        "extract_pkg_medias",
        lambda _p, _cid: Output(Status.OK, {"icon": _p}),
    )
    monkeypatch.setattr(
        watcher._pkg_utils,
        "build_pkg",
        lambda _p, _sfo, _m: Output(Status.OK, built_pkg),
    )

    result = watcher._process_pkg(pkg_path)

    assert result == built_pkg
    assert called["run"] == 1


def test_given_invalid_media_name_when_run_cycle_then_moves_media_to_error(
    init_paths, monkeypatch
):
    watcher = Watcher()
    media_path = init_paths.MEDIA_DIR_PATH / "badname.png"
    media_path.write_text("png", encoding="utf-8")
    moved = {"reasons": []}

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        watcher._file_utils,
        "move_to_error",
        lambda _path, _errors_dir, reason: moved["reasons"].append(reason) or _path,
    )

    watcher._run_cycle()

    assert "invalid_media_name" in moved["reasons"]


def test_given_orphan_media_when_run_cycle_then_moves_media_to_error(
    init_paths, monkeypatch
):
    watcher = Watcher()
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    media_path = init_paths.MEDIA_DIR_PATH / f"{content_id}_icon0.png"
    media_path.write_text("png", encoding="utf-8")
    moved = {"reasons": []}

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        watcher._file_utils,
        "move_to_error",
        lambda _path, _errors_dir, reason: moved["reasons"].append(reason) or _path,
    )

    watcher._run_cycle()

    assert "orphan_media" in moved["reasons"]


def test_given_valid_media_with_matching_pkg_when_run_cycle_then_keeps_media(
    init_paths, monkeypatch
):
    watcher = Watcher()
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    (init_paths.GAME_DIR_PATH / f"{content_id}.pkg").write_text("pkg", encoding="utf-8")
    media_path = init_paths.MEDIA_DIR_PATH / f"{content_id}_icon0.png"
    media_path.write_text("png", encoding="utf-8")
    moved = {"called": False}

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        watcher._file_utils,
        "move_to_error",
        lambda *_args, **_kwargs: moved.__setitem__("called", True),
    )

    watcher._run_cycle()

    assert moved["called"] is False


def test_given_no_changes_and_non_canonical_pkg_when_run_cycle_then_forces_processing(
    init_paths, monkeypatch
):
    watcher = Watcher()
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    processed = {"paths": [], "persisted": False}

    monkeypatch.setattr(
        cache_utils_module.CacheUtils,
        "compare_pkg_cache",
        lambda: Output(Status.SKIP, None),
    )
    monkeypatch.setattr(
        watcher,
        "_process_pkg",
        lambda _pkg_path: processed["paths"].append(_pkg_path) or None,
    )
    monkeypatch.setattr(
        watcher,
        "_persist_results",
        lambda _pkgs, _cache: processed.__setitem__("persisted", True),
    )

    watcher._run_cycle()

    assert pkg_path in processed["paths"]
    assert processed["persisted"] is True
