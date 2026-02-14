import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from hb_store_m1.models import globals as globals_module
from hb_store_m1.models.pkg.section import Section, SectionEntry
from hb_store_m1.modules.auto_organizer import AutoOrganizer
from hb_store_m1.utils.cache_utils import CacheUtils


@pytest.fixture()
def temp_globals(tmp_path, monkeypatch):
    app_root = tmp_path
    paths = globals_module._GlobalPaths(
        APP_ROOT_PATH=app_root,
        INIT_DIR_PATH=app_root / "init",
        DATA_DIR_PATH=app_root / "data",
        CACHE_DIR_PATH=app_root / "data" / "_cache",
        ERRORS_DIR_PATH=app_root / "data" / "_errors",
        LOGS_DIR_PATH=app_root / "data" / "_logs",
        PKG_DIR_PATH=app_root / "data" / "pkg",
        MEDIA_DIR_PATH=app_root / "data" / "pkg" / "_media",
        APP_DIR_PATH=app_root / "data" / "pkg" / "app",
        GAME_DIR_PATH=app_root / "data" / "pkg" / "game",
        DLC_DIR_PATH=app_root / "data" / "pkg" / "dlc",
        UPDATE_DIR_PATH=app_root / "data" / "pkg" / "update",
        SAVE_DIR_PATH=app_root / "data" / "pkg" / "save",
        UNKNOWN_DIR_PATH=app_root / "data" / "pkg" / "unknown",
    )
    files = globals_module._GlobalFiles(paths)
    envs = globals_module._GlobalEnvs(files)
    monkeypatch.setattr(globals_module.Globals, "PATHS", paths, raising=False)
    monkeypatch.setattr(globals_module.Globals, "FILES", files, raising=False)
    monkeypatch.setattr(globals_module.Globals, "ENVS", envs, raising=False)
    Section.PKG = SectionEntry("pkg", paths.PKG_DIR_PATH)
    Section.APP = SectionEntry("app", paths.APP_DIR_PATH)
    Section.DLC = SectionEntry("dlc", paths.DLC_DIR_PATH)
    Section.GAME = SectionEntry("game", paths.GAME_DIR_PATH)
    Section.SAVE = SectionEntry("save", paths.SAVE_DIR_PATH)
    Section.UNKNOWN = SectionEntry("unknown", paths.UNKNOWN_DIR_PATH)
    Section.UPDATE = SectionEntry("update", paths.UPDATE_DIR_PATH)
    Section.MEDIA = SectionEntry("_media", paths.MEDIA_DIR_PATH)
    Section.ALL = (
        Section.PKG,
        Section.APP,
        Section.DLC,
        Section.GAME,
        Section.SAVE,
        Section.UNKNOWN,
        Section.UPDATE,
        Section.MEDIA,
    )
    AutoOrganizer._SECTIONS = {section.name: section for section in Section.ALL}
    CacheUtils._SECTIONS = Section.ALL
    return paths


@pytest.fixture()
def init_paths(temp_globals):
    for p in vars(globals_module.Globals.PATHS).values():
        p.mkdir(parents=True, exist_ok=True)
    return globals_module.Globals.PATHS


@pytest.fixture()
def sample_png(tmp_path):
    path = tmp_path / "sample.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\xf8\xff\xff?"
        b"\x00\x05\xfe\x02\xfeA\xd8\xd2\xb3\x00"
        b"\x00\x00\x00IEND\xaeB`\x82"
    )
    return path


@pytest.fixture()
def sample_pkg_file(init_paths):
    pkg_path = globals_module.Globals.PATHS.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_bytes(b"pkg")
    return pkg_path


@pytest.fixture()
def sfo_data():
    return {"content_id": "UP0000-TEST00000_00-TEST000000000000", "app_type": "game"}


@pytest.fixture()
def param_sfo_lines():
    return [
        "Entry Name : string = IGNORE",
        "TITLE : string = Test Game",
        "TITLE_ID : string = CUSA00001",
        "CONTENT_ID : string = UP0000-TEST00000_00-TEST000000000000",
        "CATEGORY : string = GD",
        "PUBTOOLINFO : string = c_date=20240101",
        "VERSION : string = 01.00",
    ]
