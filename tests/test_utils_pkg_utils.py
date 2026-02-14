import subprocess
from pathlib import Path

from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFOKey
from hb_store_m1.utils.pkg_utils import PkgUtils
from hb_store_m1.helpers import pkgtool as pkgtool_module


def test_given_param_sfo_lines_when_parse_then_maps_expected_keys(
    param_sfo_lines,
):
    parsed = PkgUtils.parse_param_sfo_entries(param_sfo_lines)

    assert parsed.data[ParamSFOKey.TITLE] == "Test Game"
    assert parsed.data[ParamSFOKey.TITLE_ID] == "CUSA00001"
    assert parsed.data[ParamSFOKey.CONTENT_ID].startswith("UP0000-TEST")


def test_given_pkg_dir_when_scan_then_returns_only_pkg_files(init_paths):
    (init_paths.GAME_DIR_PATH / "one.pkg").write_text("x", encoding="utf-8")
    (init_paths.GAME_DIR_PATH / "ignore.txt").write_text("x", encoding="utf-8")

    results = PkgUtils.scan(["game"])

    assert len(results) == 1
    assert results[0].name == "one.pkg"


def test_given_validate_output_with_critical_error_when_validate_then_returns_error(
    temp_globals, monkeypatch
):
    fake_stdout = "[ERROR] Content Digest mismatch"

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
    param_sfo, medias = result.content
    assert param_sfo.data[ParamSFOKey.CONTENT_ID].startswith("UP0000-TEST")
    assert medias
