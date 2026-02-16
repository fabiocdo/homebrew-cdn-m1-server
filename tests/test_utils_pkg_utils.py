import subprocess
from pathlib import Path

from hb_store_m1.helpers import pkgtool as pkgtool_module
from hb_store_m1.models.output import Output
from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFO
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFOKey
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntryKey
from hb_store_m1.utils.pkg_utils import PkgUtils


def test_given_param_sfo_lines_when_parse_then_maps_expected_keys(
    param_sfo_lines,
):
    parsed = PkgUtils.parse_param_sfo_entries(param_sfo_lines)

    assert parsed.data[ParamSFOKey.TITLE] == "Test Game"
    assert parsed.data[ParamSFOKey.TITLE_ID] == "CUSA00001"
    assert parsed.data[ParamSFOKey.CONTENT_ID].startswith("UP0000-TEST")


def test_given_invalid_and_unknown_sfo_lines_when_parse_then_ignores_them():
    parsed = PkgUtils.parse_param_sfo_entries(
        [
            "invalid line",
            "UNKNOWN_FIELD : string = value",
            "TITLE : string = Game",
        ]
    )

    assert parsed.data[ParamSFOKey.TITLE] == "Game"


def test_given_malformed_and_unknown_entries_when_list_pkg_entries_then_ignores(
    monkeypatch,
):
    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "short",
                "0 0 0 2 UNKNOWN_ENTRY",
                "0 0 0 3 PARAM_SFO",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)

    entries = PkgUtils._list_pkg_entries(Path("x.pkg"))

    assert entries == {PKGEntryKey.PARAM_SFO: "3"}


def test_given_pkg_dir_when_scan_then_returns_only_pkg_files(init_paths):
    (init_paths.GAME_DIR_PATH / "one.pkg").write_text("x", encoding="utf-8")
    (init_paths.GAME_DIR_PATH / "ignore.txt").write_text("x", encoding="utf-8")

    results = PkgUtils.scan(["game"])

    assert len(results) == 1
    assert results[0].name == "one.pkg"


def test_given_validate_output_with_critical_error_when_validate_then_returns_error(
    temp_globals, monkeypatch
):
    fake_stdout = "[ERROR] PKG Header Digest mismatch"

    def fake_validate(_pkg):
        return subprocess.CompletedProcess([], 0, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "validate_pkg", fake_validate)

    result = PkgUtils.validate(Path("game.pkg"))

    assert result.status is Status.ERROR


def test_given_validate_output_with_non_critical_error_when_validate_then_returns_warn(
    temp_globals, monkeypatch
):
    fake_stdout = "[ERROR] PIC0_PNG digest mismatch"

    def fake_validate(_pkg):
        return subprocess.CompletedProcess([], 0, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "validate_pkg", fake_validate)

    result = PkgUtils.validate(Path("game.pkg"))

    assert result.status is Status.WARN


def test_given_validate_output_without_errors_when_validate_then_returns_ok(
    temp_globals, monkeypatch
):
    def fake_validate(_pkg):
        return subprocess.CompletedProcess([], 0, stdout="OK", stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "validate_pkg", fake_validate)

    result = PkgUtils.validate(Path("game.pkg"))

    assert result.status is Status.OK


def test_given_pkgtool_failure_when_validate_then_returns_error(
    temp_globals, monkeypatch
):
    def fake_validate(_pkg):
        raise subprocess.CalledProcessError(1, ["pkgtool"])

    monkeypatch.setattr(pkgtool_module.PKGTool, "validate_pkg", fake_validate)

    result = PkgUtils.validate(Path("game.pkg"))

    assert result.status is Status.ERROR


def test_given_pkgtool_non_zero_with_non_critical_output_when_validate_then_returns_warn(
    temp_globals, monkeypatch
):
    def fake_validate(_pkg):
        raise subprocess.CalledProcessError(
            1,
            ["pkgtool"],
            output="[ERROR] PIC0_PNG digest mismatch",
            stderr="",
        )

    monkeypatch.setattr(pkgtool_module.PKGTool, "validate_pkg", fake_validate)

    result = PkgUtils.validate(Path("game.pkg"))

    assert result.status is Status.WARN


def test_given_pkg_data_when_extract_then_returns_pkg_model(
    init_paths, param_sfo_lines, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "0 0 0 1 PARAM_SFO",
                "0 0 0 2 ICON0_PNG",
                "0 0 0 3 PIC0_PNG",
                "0 0 0 4 PIC1_PNG",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    def fake_list_sfo(_sfo):
        return subprocess.CompletedProcess(
            [], 0, stdout="\n".join(param_sfo_lines), stderr=""
        )

    def fake_extract(_pkg, _index, output_file):
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".png":
            output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        else:
            output_path.write_text("sfo", encoding="utf-8")
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)
    monkeypatch.setattr(pkgtool_module.PKGTool, "list_sfo_entries", fake_list_sfo)
    monkeypatch.setattr(pkgtool_module.PKGTool, "extract_pkg_entry", fake_extract)

    result = PkgUtils.extract_pkg_data(pkg_path)

    assert result.status is Status.OK
    param_sfo = result.content
    assert param_sfo.data[ParamSFOKey.CONTENT_ID].startswith("UP0000-TEST")


def test_given_pkg_when_extract_medias_then_returns_paths(
    init_paths, param_sfo_lines, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "0 0 0 1 PARAM_SFO",
                "0 0 0 2 ICON0_PNG",
                "0 0 0 3 PIC0_PNG",
                "0 0 0 4 PIC1_PNG",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    def fake_extract(_pkg, _index, output_file):
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)
    monkeypatch.setattr(pkgtool_module.PKGTool, "extract_pkg_entry", fake_extract)

    result = PkgUtils.extract_pkg_medias(
        pkg_path, "UP0000-TEST00000_00-TEST000000000000"
    )

    assert result.status is Status.OK
    assert result.content


def test_given_read_content_id_when_validate_fails_then_returns_none(monkeypatch):
    monkeypatch.setattr(PkgUtils, "validate", lambda _pkg: Output(Status.ERROR, None))

    assert PkgUtils.read_content_id(Path("x.pkg")) is None


def test_given_read_content_id_when_extract_fails_then_returns_none(monkeypatch):
    monkeypatch.setattr(PkgUtils, "validate", lambda _pkg: Output(Status.OK, None))
    monkeypatch.setattr(
        PkgUtils, "extract_pkg_data", lambda _pkg: Output(Status.ERROR, None)
    )

    assert PkgUtils.read_content_id(Path("x.pkg")) is None


def test_given_read_content_id_when_validate_warn_then_extracts(monkeypatch):
    sfo = ParamSFO({ParamSFOKey.CONTENT_ID: "UP0000-TEST00000_00-TEST000000000000"})
    monkeypatch.setattr(PkgUtils, "validate", lambda _pkg: Output(Status.WARN, None))
    monkeypatch.setattr(
        PkgUtils, "extract_pkg_data", lambda _pkg: Output(Status.OK, sfo)
    )

    content_id = PkgUtils.read_content_id(Path("x.pkg"))

    assert content_id == "UP0000-TEST00000_00-TEST000000000000"


def test_given_read_content_id_when_extract_succeeds_then_does_not_validate(monkeypatch):
    sfo = ParamSFO({ParamSFOKey.CONTENT_ID: "UP0000-TEST00000_00-TEST000000000000"})
    validate_called = {"called": False}
    monkeypatch.setattr(
        PkgUtils,
        "validate",
        lambda _pkg: validate_called.__setitem__("called", True)
        or Output(Status.OK, None),
    )
    monkeypatch.setattr(
        PkgUtils, "extract_pkg_data", lambda _pkg: Output(Status.OK, sfo)
    )

    content_id = PkgUtils.read_content_id(Path("x.pkg"))

    assert content_id == "UP0000-TEST00000_00-TEST000000000000"
    assert validate_called["called"] is False


def test_given_read_content_id_when_extract_fails_then_validates_in_fallback(monkeypatch):
    validate_called = {"called": False}
    monkeypatch.setattr(
        PkgUtils,
        "validate",
        lambda _pkg: validate_called.__setitem__("called", True)
        or Output(Status.ERROR, None),
    )
    monkeypatch.setattr(
        PkgUtils, "extract_pkg_data", lambda _pkg: Output(Status.ERROR, None)
    )

    content_id = PkgUtils.read_content_id(Path("x.pkg"))

    assert content_id is None
    assert validate_called["called"] is True


def test_given_missing_section_root_when_scan_then_skips(init_paths):
    # "app" directory exists in fixture; remove to hit the skip branch.
    init_paths.APP_DIR_PATH.rmdir()

    scanned = PkgUtils.scan(["app"])

    assert scanned == []


def test_given_missing_pkg_when_extract_data_then_returns_not_found():
    result = PkgUtils.extract_pkg_data(Path("missing.pkg"))

    assert result.status is Status.NOT_FOUND


def test_given_pkgtool_exception_when_extract_data_then_returns_error(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(
        pkgtool_module.PKGTool,
        "list_pkg_entries",
        lambda _pkg: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = PkgUtils.extract_pkg_data(pkg_path)

    assert result.status is Status.ERROR


def test_given_missing_pkg_when_extract_medias_then_returns_not_found():
    result = PkgUtils.extract_pkg_medias(Path("missing.pkg"), "X")

    assert result.status is Status.NOT_FOUND


def test_given_missing_content_id_when_extract_medias_then_returns_error(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    result = PkgUtils.extract_pkg_medias(pkg_path, "")

    assert result.status is Status.ERROR


def test_given_missing_critical_media_entry_when_extract_medias_then_returns_error(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "0 0 0 3 PIC0_PNG",
                "0 0 0 4 PIC1_PNG",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)

    result = PkgUtils.extract_pkg_medias(
        pkg_path, "UP0000-TEST00000_00-TEST000000000000"
    )

    assert result.status is Status.ERROR


def test_given_optional_media_missing_when_extract_medias_then_sets_none(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "0 0 0 2 ICON0_PNG",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    def fake_extract(_pkg, _index, output_file):
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)
    monkeypatch.setattr(pkgtool_module.PKGTool, "extract_pkg_entry", fake_extract)

    result = PkgUtils.extract_pkg_medias(
        pkg_path, "UP0000-TEST00000_00-TEST000000000000"
    )

    assert result.status is Status.OK
    assert result.content[PKGEntryKey.PIC0_PNG] is None
    assert result.content[PKGEntryKey.PIC1_PNG] is None


def test_given_existing_media_files_when_extract_medias_then_reuses_paths(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    content_id = "UP0000-TEST00000_00-TEST000000000000"
    for suffix in ("_icon0.png", "_pic0.png", "_pic1.png"):
        (init_paths.MEDIA_DIR_PATH / f"{content_id}{suffix}").write_bytes(
            b"\x89PNG\r\n\x1a\n"
        )

    def fake_list_entries(_pkg):
        stdout = "\n".join(
            [
                "header",
                "0 0 0 2 ICON0_PNG",
                "0 0 0 3 PIC0_PNG",
                "0 0 0 4 PIC1_PNG",
            ]
        )
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    monkeypatch.setattr(pkgtool_module.PKGTool, "list_pkg_entries", fake_list_entries)

    result = PkgUtils.extract_pkg_medias(pkg_path, content_id)

    assert result.status is Status.OK
    assert result.content[PKGEntryKey.ICON0_PNG].exists()


def test_given_pkgtool_exception_when_extract_medias_then_returns_error(
    init_paths, monkeypatch
):
    pkg_path = init_paths.GAME_DIR_PATH / "sample.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    monkeypatch.setattr(
        pkgtool_module.PKGTool,
        "list_pkg_entries",
        lambda _pkg: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = PkgUtils.extract_pkg_medias(
        pkg_path, "UP0000-TEST00000_00-TEST000000000000"
    )

    assert result.status is Status.ERROR


def test_given_param_and_medias_when_build_pkg_then_returns_model():
    sfo = ParamSFO(
        {
            ParamSFOKey.TITLE: "t",
            ParamSFOKey.TITLE_ID: "CUSA00001",
            ParamSFOKey.CONTENT_ID: "UP0000-TEST00000_00-TEST000000000000",
            ParamSFOKey.CATEGORY: "GD",
            ParamSFOKey.VERSION: "01.00",
            ParamSFOKey.APP_VER: "01.01",
            ParamSFOKey.PUBTOOLINFO: "",
        }
    )
    medias = {
        PKGEntryKey.ICON0_PNG: Path("/tmp/icon0.png"),
        PKGEntryKey.PIC0_PNG: None,
        PKGEntryKey.PIC1_PNG: None,
    }

    result = PkgUtils.build_pkg(Path("/tmp/x.pkg"), sfo, medias)

    assert result.status is Status.OK
    assert result.content.content_id == "UP0000-TEST00000_00-TEST000000000000"
    assert result.content.version == "01.01"


def test_given_version_and_app_ver_when_resolve_pkg_version_then_uses_highest():
    assert (
        PkgUtils.resolve_pkg_version(
            {ParamSFOKey.VERSION: "01.00", ParamSFOKey.APP_VER: "01.23"}
        )
        == "01.23"
    )
    assert (
        PkgUtils.resolve_pkg_version(
            {ParamSFOKey.VERSION: "02.00", ParamSFOKey.APP_VER: "01.99"}
        )
        == "02.00"
    )


def test_given_missing_or_invalid_versions_when_resolve_pkg_version_then_fallbacks():
    assert (
        PkgUtils.resolve_pkg_version(
            {ParamSFOKey.VERSION: "", ParamSFOKey.APP_VER: "01.05"}
        )
        == "01.05"
    )
    assert (
        PkgUtils.resolve_pkg_version(
            {ParamSFOKey.VERSION: "01.00", ParamSFOKey.APP_VER: ""}
        )
        == "01.00"
    )
    assert (
        PkgUtils.resolve_pkg_version(
            {ParamSFOKey.VERSION: "foo", ParamSFOKey.APP_VER: "01.02"}
        )
        == "01.02"
    )
