from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import ClassVar, cast, final, override

from homebrew_cdn_m1_server.domain.models.results import ProbeResult
from homebrew_cdn_m1_server.domain.protocols.package_probe_protocol import PackageProbeProtocol
from homebrew_cdn_m1_server.domain.models.content_id import ContentId
from homebrew_cdn_m1_server.domain.models.app_type import AppType


_CONTROL_CHARACTERS = {chr(code) for code in range(0x00, 0x20)}
_CONTROL_CHARACTERS.add(chr(0x7F))


def normalize_text(value: str) -> str:
    raw = str(value or "")
    normalized = unicodedata.normalize("NFKC", raw)
    cleaned = "".join(
        ch for ch in normalized if ch not in _CONTROL_CHARACTERS or ch in {"\t", "\n", "\r"}
    )
    return cleaned.strip()


@final
class PkgtoolGateway(PackageProbeProtocol):
    _PARAM_REGEX: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<name>[^:]+?)\s*:\s*[^=]*=\s*(?P<value>.*)$"
    )
    _VERSION_PARTS_REGEX: ClassVar[re.Pattern[str]] = re.compile(r"\d+")

    def __init__(
        self,
        pkgtool_bin: Path,
        timeout_seconds: int | None,
        media_dir: Path,
    ) -> None:
        self._pkgtool_bin = pkgtool_bin
        if timeout_seconds is None:
            self._timeout_seconds: int | None = None
        else:
            self._timeout_seconds = max(1, int(timeout_seconds))
        self._media_dir = media_dir

    @staticmethod
    def _normalize_entry_name(name: str) -> str:
        return str(name or "").strip().upper().replace(".", "_")

    def _run(self, command: str, *args: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        if not self._pkgtool_bin.exists():
            raise FileNotFoundError(f"pkgtool binary not found: {self._pkgtool_bin}")
        return subprocess.run(
            [str(self._pkgtool_bin), command, *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
            timeout=(timeout if timeout is not None else self._timeout_seconds),
            env={"DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1"},
        )

    def _list_entries(self, pkg_path: Path) -> dict[str, str]:
        result = self._run("pkg_listentries", str(pkg_path))
        entries: dict[str, str] = {}
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            index = parts[3]
            name = parts[4]
            entries[self._normalize_entry_name(name)] = index
        return entries

    @classmethod
    def parse_sfo_entries(cls, lines: list[str]) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for line in lines:
            match = cls._PARAM_REGEX.match(line.strip())
            if not match:
                continue
            key = normalize_text(match.group("name"))
            if key == "Entry Name":
                continue
            value = normalize_text(match.group("value"))
            parsed[key] = value
        return parsed

    @classmethod
    def _version_key(cls, raw: str) -> tuple[int, ...] | None:
        text = str(raw or "").strip()
        if not text:
            return None
        matches = cast(list[str], cls._VERSION_PARTS_REGEX.findall(text))
        parts = [int(item) for item in matches]
        if not parts:
            return None
        while len(parts) > 1 and parts[-1] == 0:
            _ = parts.pop()
        return tuple(parts)

    @classmethod
    def _resolve_version(cls, fields: dict[str, str]) -> str:
        version = str(fields.get("VERSION") or "").strip()
        app_ver = str(fields.get("APP_VER") or "").strip()

        if not version:
            return app_ver
        if not app_ver:
            return version

        left = cls._version_key(app_ver)
        right = cls._version_key(version)
        if left is None or right is None:
            return app_ver if app_ver > version else version
        max_len = max(len(left), len(right))
        left = left + (0,) * (max_len - len(left))
        right = right + (0,) * (max_len - len(right))
        return app_ver if left >= right else version

    @staticmethod
    def _release_date(pubtoolinfo: str) -> str:
        match = re.search(r"\bc_date=(\d{8})\b", pubtoolinfo or "")
        if not match:
            return "1970-01-01"
        ymd = match.group(1)
        return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"

    @staticmethod
    def _media_name(base: str, suffix: str) -> str:
        return f"{base}_{suffix}.png"

    def _extract_media(
        self,
        pkg_path: Path,
        entries: dict[str, str],
        content_id: str,
    ) -> tuple[Path | None, Path | None, Path | None]:
        self._media_dir.mkdir(parents=True, exist_ok=True)

        icon0_path = self._media_dir / self._media_name(content_id, "icon0")
        pic0_path = self._media_dir / self._media_name(content_id, "pic0")
        pic1_path = self._media_dir / self._media_name(content_id, "pic1")

        targets = [
            ("ICON0_PNG", icon0_path, True),
            ("PIC0_PNG", pic0_path, False),
            ("PIC1_PNG", pic1_path, False),
        ]

        extracted: list[Path | None] = []
        for entry_name, out_path, required in targets:
            entry_index = entries.get(entry_name)
            if not entry_index:
                if required:
                    raise ValueError(f"{entry_name} not found in package")
                extracted.append(None)
                continue
            if out_path.exists():
                extracted.append(out_path)
                continue
            _ = self._run("pkg_extractentry", str(pkg_path), entry_index, str(out_path))
            extracted.append(out_path)

        return extracted[0], extracted[1], extracted[2]

    @override
    def probe(self, pkg_path: Path) -> ProbeResult:
        entries = self._list_entries(pkg_path)
        param_index = entries.get("PARAM_SFO")
        if not param_index:
            raise ValueError("PARAM.SFO not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            sfo_path = Path(temp_dir) / "param.sfo"
            _ = self._run("pkg_extractentry", str(pkg_path), param_index, str(sfo_path))
            sfo_raw = sfo_path.read_bytes()
            sfo_lines = self._run("sfo_listentries", str(sfo_path)).stdout.splitlines()

        fields = self.parse_sfo_entries(sfo_lines)

        content_id = ContentId.parse(fields.get("CONTENT_ID", ""))
        title_id = normalize_text(fields.get("TITLE_ID", ""))
        title = normalize_text(fields.get("TITLE", ""))
        category = normalize_text(fields.get("CATEGORY", "")).upper()
        version = self._resolve_version(fields)
        pubtoolinfo = normalize_text(fields.get("PUBTOOLINFO", ""))
        system_ver = normalize_text(fields.get("SYSTEM_VER", ""))
        app_type = AppType.from_category(category)
        release_date = self._release_date(pubtoolinfo)

        if not title_id or not title:
            raise ValueError("Missing required TITLE_ID/TITLE in PARAM.SFO")

        sfo_json = json.dumps(fields, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        sfo_hash = hashlib.md5(sfo_json.encode("utf-8")).hexdigest()

        icon0, pic0, pic1 = self._extract_media(pkg_path, entries, content_id.value)

        return ProbeResult(
            content_id=content_id,
            title_id=title_id,
            title=title,
            category=category,
            version=version,
            pubtoolinfo=pubtoolinfo,
            system_ver=system_ver,
            app_type=app_type,
            release_date=release_date,
            sfo_fields=fields,
            sfo_raw=sfo_raw,
            sfo_hash=sfo_hash,
            icon0_path=icon0,
            pic0_path=pic0,
            pic1_path=pic1,
        )
