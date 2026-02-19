# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from homebrew_cdn_m1_server.application.gateways.pkgtool_gateway import PkgtoolGateway
from homebrew_cdn_m1_server.domain.models.app_type import AppType


def _gateway(temp_workspace: Path) -> tuple[PkgtoolGateway, Path]:
    pkgtool_bin = temp_workspace / "bin" / "pkgtool"
    pkgtool_bin.parent.mkdir(parents=True, exist_ok=True)
    _ = pkgtool_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    media_dir = temp_workspace / "data" / "share" / "pkg" / "media"
    gateway = PkgtoolGateway(pkgtool_bin=pkgtool_bin, timeout_seconds=10, media_dir=media_dir)
    return gateway, pkgtool_bin


def test_pkgtool_gateway_run_given_missing_binary_when_called_then_raises(
    temp_workspace: Path,
) -> None:
    gateway = PkgtoolGateway(
        pkgtool_bin=temp_workspace / "bin" / "missing-pkgtool",
        timeout_seconds=10,
        media_dir=temp_workspace / "media",
    )
    with pytest.raises(FileNotFoundError, match="pkgtool binary not found"):
        _ = gateway._run("pkg_listentries", "/tmp/fake.pkg")


def test_pkgtool_gateway_list_entries_given_output_when_called_then_parses(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    output = "\n".join(
        [
            "Header",
            "0 0 0 11 PARAM.SFO",
            "0 0 0 12 ICON0.PNG",
            "x",
        ]
    )

    def _fake_run(
        command: str,
        *args: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        return subprocess.CompletedProcess(
            args=[command, *args],
            returncode=0,
            stdout=output,
            stderr="",
        )

    monkeypatch.setattr(gateway, "_run", _fake_run)
    entries = gateway._list_entries(pkg_path)
    assert entries == {"PARAM_SFO": "11", "ICON0_PNG": "12"}


def test_pkgtool_gateway_version_and_release_helpers_when_called_then_normalize_values() -> None:
    assert PkgtoolGateway._resolve_version({"VERSION": "01.00", "APP_VER": "01.02"}) == "01.02"
    assert PkgtoolGateway._resolve_version({"VERSION": "bad", "APP_VER": "zzz"}) == "zzz"
    assert PkgtoolGateway._release_date("abc c_date=20250102 xyz") == "2025-01-02"
    assert PkgtoolGateway._release_date("") == "1970-01-01"


def test_pkgtool_gateway_extract_media_given_required_missing_when_called_then_raises(
    temp_workspace: Path,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    with pytest.raises(ValueError, match="ICON0_PNG not found"):
        _ = gateway._extract_media(
            pkg_path, {}, "UP0000-TEST00000_00-TEST000000000000", AppType.GAME
        )


def test_pkgtool_gateway_extract_media_given_update_without_icon0_when_called_then_returns_none(
    temp_workspace: Path,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    icon0, pic0, pic1 = gateway._extract_media(
        pkg_path, {}, "UP0000-TEST00000_00-TEST000000000000", AppType.UPDATE
    )

    assert icon0 is None
    assert pic0 is None
    assert pic1 is None


def test_pkgtool_gateway_extract_media_given_entries_when_called_then_extracts_and_returns(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    def _fake_run(
        command: str,
        *args: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        if command == "pkg_extractentry":
            out = Path(args[2])
            out.parent.mkdir(parents=True, exist_ok=True)
            _ = out.write_bytes(b"img")
        return subprocess.CompletedProcess(
            args=[command, *args],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(gateway, "_run", _fake_run)
    icon0, pic0, pic1 = gateway._extract_media(
        pkg_path,
        entries={"ICON0_PNG": "10", "PIC0_PNG": "11"},
        content_id="UP0000-TEST00000_00-TEST000000000000",
        app_type=AppType.GAME,
    )

    assert icon0 is not None and icon0.exists() is True
    assert pic0 is not None and pic0.exists() is True
    assert pic1 is None


def test_pkgtool_gateway_probe_given_valid_sfo_when_called_then_returns_probe_result(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    def _list_entries(_pkg: Path) -> dict[str, str]:
        return {"PARAM_SFO": "10"}

    def _extract_media(
        _pkg: Path,
        _entries: dict[str, str],
        _content_id: str,
        _app_type: AppType,
    ) -> tuple[Path | None, Path | None, Path | None]:
        return (None, None, None)

    def _fake_run(
        command: str,
        *args: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        if command == "pkg_extractentry":
            out = Path(args[2])
            _ = out.write_bytes(b"sfo-bytes")
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout="", stderr=""
            )
        if command == "sfo_listentries":
            stdout = "\n".join(
                [
                    "CONTENT_ID : utf8 = UP0000-TEST00000_00-TEST000000000000",
                    "TITLE_ID : utf8 = CUSA00001",
                    "TITLE : utf8 = Test Game",
                    "CATEGORY : utf8 = gd",
                    "VERSION : utf8 = 01.00",
                    "APP_VER : utf8 = 01.02",
                    "PUBTOOLINFO : utf8 = c_date=20250101",
                    "SYSTEM_VER : utf8 = 0x05050000",
                ]
            )
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout=stdout, stderr=""
            )
        return subprocess.CompletedProcess(
            args=[command, *args], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(gateway, "_list_entries", _list_entries)
    monkeypatch.setattr(gateway, "_extract_media", _extract_media)
    monkeypatch.setattr(gateway, "_run", _fake_run)

    result = gateway.probe(pkg_path)
    assert result.content_id.value == "UP0000-TEST00000_00-TEST000000000000"
    assert result.title_id == "CUSA00001"
    assert result.title == "Test Game"
    assert result.version == "01.02"
    assert result.release_date == "2025-01-01"
    assert result.sfo_raw == b"sfo-bytes"


def test_pkgtool_gateway_probe_given_missing_required_fields_when_called_then_raises(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    def _list_entries(_pkg: Path) -> dict[str, str]:
        return {"PARAM_SFO": "10"}

    def _extract_media(
        _pkg: Path,
        _entries: dict[str, str],
        _content_id: str,
        _app_type: AppType,
    ) -> tuple[Path | None, Path | None, Path | None]:
        return (None, None, None)

    def _fake_run(
        command: str,
        *args: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        if command == "pkg_extractentry":
            out = Path(args[2])
            _ = out.write_bytes(b"sfo-bytes")
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout="", stderr=""
            )
        if command == "sfo_listentries":
            stdout = "CONTENT_ID : utf8 = UP0000-TEST00000_00-TEST000000000000"
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout=stdout, stderr=""
            )
        return subprocess.CompletedProcess(
            args=[command, *args], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(gateway, "_list_entries", _list_entries)
    monkeypatch.setattr(gateway, "_extract_media", _extract_media)
    monkeypatch.setattr(gateway, "_run", _fake_run)

    with pytest.raises(ValueError, match="Missing required TITLE_ID/TITLE"):
        _ = gateway.probe(pkg_path)


def test_pkgtool_gateway_probe_given_update_without_icon0_when_called_then_returns_without_icon(
    temp_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = _gateway(temp_workspace)
    pkg_path = temp_workspace / "A.pkg"
    _ = pkg_path.write_bytes(b"x")

    def _list_entries(_pkg: Path) -> dict[str, str]:
        return {"PARAM_SFO": "10"}

    def _fake_run(
        command: str,
        *args: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        if command == "pkg_extractentry":
            out = Path(args[2])
            _ = out.write_bytes(b"sfo-bytes")
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout="", stderr=""
            )
        if command == "sfo_listentries":
            stdout = "\n".join(
                [
                    "CONTENT_ID : utf8 = UP0000-TEST00000_00-TEST000000000000",
                    "TITLE_ID : utf8 = CUSA00001",
                    "TITLE : utf8 = Test Update",
                    "CATEGORY : utf8 = gp",
                    "VERSION : utf8 = 01.00",
                    "APP_VER : utf8 = 01.01",
                    "PUBTOOLINFO : utf8 = c_date=20250101",
                    "SYSTEM_VER : utf8 = 0x05050000",
                ]
            )
            return subprocess.CompletedProcess(
                args=[command, *args], returncode=0, stdout=stdout, stderr=""
            )
        return subprocess.CompletedProcess(
            args=[command, *args], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(gateway, "_list_entries", _list_entries)
    monkeypatch.setattr(gateway, "_run", _fake_run)

    result = gateway.probe(pkg_path)

    assert result.app_type == AppType.UPDATE
    assert result.icon0_path is None
    assert result.pic0_path is None
    assert result.pic1_path is None
