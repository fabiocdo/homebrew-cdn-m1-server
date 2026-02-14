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
    assert (
        captured["kwargs"]["timeout"] == Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_SECONDS
    )
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


def test_given_large_pkg_when_validate_timeout_then_scales_by_size(
    temp_globals, monkeypatch, tmp_path
):
    pkg_path = tmp_path / "large.pkg"
    pkg_path.write_bytes(b"x")

    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_SECONDS",
        300,
        raising=False,
    )
    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS",
        45,
        raising=False,
    )
    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS",
        3600,
        raising=False,
    )

    class _Stat:
        st_size = 25 * 1024**3

    monkeypatch.setattr(Path, "stat", lambda _self: _Stat())

    timeout = PKGTool._validate_timeout_seconds(pkg_path)

    assert timeout == 1125


def test_given_huge_pkg_when_validate_timeout_then_respects_max(
    temp_globals, monkeypatch, tmp_path
):
    pkg_path = tmp_path / "huge.pkg"
    pkg_path.write_bytes(b"x")

    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_SECONDS",
        300,
        raising=False,
    )
    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS",
        90,
        raising=False,
    )
    monkeypatch.setattr(
        Globals.ENVS,
        "PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS",
        600,
        raising=False,
    )

    class _Stat:
        st_size = 20 * 1024**3

    monkeypatch.setattr(Path, "stat", lambda _self: _Stat())

    timeout = PKGTool._validate_timeout_seconds(pkg_path)

    assert timeout == 600
