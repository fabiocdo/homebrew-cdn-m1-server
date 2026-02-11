import subprocess
from pathlib import Path

from hb_store_m1.helpers.pkgtool import PKGTool
from hb_store_m1.models.globals import Globals


def test_given_pkg_path_when_validate_pkg_then_calls_pkgtool_with_expected_args(
    temp_globals, monkeypatch
):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    pkg_path = Path("sample.pkg")
    PKGTool.validate_pkg(pkg_path)

    assert captured["args"][0] == Globals.FILES.PKGTOOL_FILE_PATH
    assert captured["args"][1] == "pkg_validate"
    assert captured["args"][2] == str(pkg_path)
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["timeout"] == 120
    assert captured["kwargs"]["env"] == {"DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1"}


def test_given_pkg_path_when_list_entries_then_calls_pkgtool_with_list_command(
    temp_globals, monkeypatch
):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    pkg_path = Path("sample.pkg")
    PKGTool.list_pkg_entries(pkg_path)

    assert captured["args"][1] == "pkg_listentries"
    assert captured["args"][2] == str(pkg_path)


def test_given_sfo_path_when_list_sfo_entries_then_calls_pkgtool_with_sfo_command(
    temp_globals, monkeypatch
):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    sfo_path = Path("param.sfo")
    PKGTool.list_sfo_entries(sfo_path)

    assert captured["args"][1] == "sfo_listentries"
    assert captured["args"][2] == str(sfo_path)
