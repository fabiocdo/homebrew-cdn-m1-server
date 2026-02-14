import pytest

from hb_store_m1.models.output import Output, Status
from hb_store_m1.modules.watcher import Watcher
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFO, ParamSFOKey
from hb_store_m1.utils import cache_utils as cache_utils_module
from hb_store_m1.utils import pkg_utils as pkg_utils_module
from hb_store_m1.utils import db_utils as db_utils_module
from hb_store_m1.utils import fpkgi_utils as fpkgi_utils_module
from hb_store_m1.utils import file_utils as file_utils_module
from hb_store_m1.modules import auto_organizer as auto_organizer_module


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


def test_given_changes_when_run_cycle_then_updates_cache(
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
                "added": {"game": ["UP0000-TEST00000_00-TEST000000000000"]},
                "updated": {},
                "removed": {},
                "current_files": {
                    "game": {
                        "UP0000-TEST00000_00-TEST000000000000": "sample.pkg"
                    }
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
