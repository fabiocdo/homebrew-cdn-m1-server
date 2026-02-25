from __future__ import annotations

from collections.abc import Sequence
import json
import re
from pathlib import Path
from typing import ClassVar, cast, final, override

from homebrew_cdn_m1_server.application.exporters.fpkgi_contract import (
    FpkgiDocument,
    FpkgiItem,
    build_fpkgi_schema,
)
from homebrew_cdn_m1_server.domain.protocols.output_exporter_protocol import OutputExporterProtocol
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem


@final
class FpkgiJsonExporter(OutputExporterProtocol):
    target: OutputTarget = OutputTarget.FPKGI
    _MANAGED_STEMS: ClassVar[tuple[str, ...]] = (
        "APPS",
        "DEMOS",
        "DLC",
        "EMULATORS",
        "GAMES",
        "HOMEBREW",
        "PS1",
        "PS2",
        "PS5",
        "PSP",
        "SAVES",
        "THEMES",
        "UPDATES",
    )
    _LEGACY_STEMS_TO_CLEAN: ClassVar[tuple[str, ...]] = ("UNKNOWN",)

    _STEM_BY_APP_TYPE: ClassVar[dict[str, str]] = {
        "app": "APPS",
        "dlc": "DLC",
        "game": "GAMES",
        "save": "SAVES",
        "update": "UPDATES",
        "unknown": "HOMEBREW",
    }

    _REGION_BY_PREFIX: ClassVar[dict[str, str]] = {
        "UP": "USA",
        "UB": "USA",
        "EP": "EUR",
        "JP": "JAP",
        "HP": "ASIA",
        "AP": "ASIA",
        "KP": "ASIA",
    }
    _HEX_SYSTEM_VER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9A-Fa-f]{8}$")
    _DOT_SYSTEM_VER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\d+\.\d+(?:\.\d+)?$")

    def __init__(self, output_dir: Path, base_url: str, schema_path: Path) -> None:
        self._output_dir = output_dir
        self._base_url = base_url.rstrip("/")
        self._schema_path = schema_path
        self._validate_schema_contract()

    def _validate_schema_contract(self) -> None:
        if not self._schema_path.exists():
            raise FileNotFoundError(f"FPKGI schema not found: {self._schema_path}")

        raw = self._schema_path.read_text("utf-8")
        actual = cast(object, json.loads(raw))
        if not isinstance(actual, dict):
            raise ValueError(f"FPKGI schema must be a JSON object: {self._schema_path}")

        expected = build_fpkgi_schema()
        if actual != expected:
            raise ValueError(
                f"FPKGI schema file is out of sync with exporter contract: {self._schema_path}"
            )

    def _pkg_url(self, item: CatalogItem) -> str:
        return f"{self._base_url}/pkg/{item.app_type.value}/{item.content_id.value}.pkg"

    def _cover_url(self, item: CatalogItem) -> str:
        return f"{self._base_url}/pkg/media/{item.content_id.value}_icon0.png"

    @classmethod
    def _region(cls, content_id: str) -> str | None:
        return cls._REGION_BY_PREFIX.get(content_id[:2].upper())

    @staticmethod
    def _release(value: str) -> str:
        try:
            yyyy, mm, dd = (value or "").split("-", 2)
        except ValueError:
            return value or ""
        return f"{mm}-{dd}-{yyyy}"

    @staticmethod
    def _byte_to_decimal(byte_text: str) -> int:
        high = int(byte_text[0], 16)
        low = int(byte_text[1], 16)
        if high <= 9 and low <= 9:
            return (high * 10) + low
        return int(byte_text, 16)

    @classmethod
    def _decode_system_ver_hex(cls, hex_value: str) -> str:
        major = cls._byte_to_decimal(hex_value[0:2])
        minor = cls._byte_to_decimal(hex_value[2:4])
        return f"{major:02d}.{minor:02d}"

    @staticmethod
    def _normalize_min_fw_dot(value: str) -> str:
        parts = str(value or "").split(".")
        if len(parts) < 2:
            return value
        try:
            major = int(parts[0])
            minor = int(parts[1])
        except ValueError:
            return value
        return f"{major:02d}.{minor:02d}"

    @classmethod
    def _normalize_min_fw(cls, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if cls._DOT_SYSTEM_VER_PATTERN.fullmatch(raw):
            return cls._normalize_min_fw_dot(raw)

        hex_value = raw[2:] if raw.lower().startswith("0x") else raw
        if cls._HEX_SYSTEM_VER_PATTERN.fullmatch(hex_value):
            return cls._decode_system_ver_hex(hex_value)

        if raw.isdigit() and len(raw) > 8:
            try:
                return cls._decode_system_ver_hex(f"{int(raw):08X}"[-8:])
            except ValueError:
                return raw
        return raw

    @staticmethod
    def _format_size(item: CatalogItem) -> int:
        return int(item.pkg_size)

    @override
    def export(self, items: Sequence[CatalogItem]) -> list[Path]:
        grouped: dict[str, dict[str, FpkgiItem]] = {
            stem: {} for stem in self._MANAGED_STEMS
        }
        for item in items:
            app_type = item.app_type.value
            stem = self._STEM_BY_APP_TYPE.get(app_type, app_type.upper())
            payload = grouped.setdefault(stem, {})
            pkg_url = self._pkg_url(item)
            payload[pkg_url] = FpkgiItem(
                title_id=item.title_id,
                region=self._region(item.content_id.value),
                name=item.title,
                version=item.version,
                release=self._release(item.release_date),
                size=self._format_size(item),
                min_fw=self._normalize_min_fw(item.system_ver),
                cover_url=self._cover_url(item),
            )

        self._output_dir.mkdir(parents=True, exist_ok=True)

        exported: list[Path] = []
        generated_paths: set[Path] = set()
        for stem, data in sorted(grouped.items()):
            destination = self._output_dir / f"{stem}.json"
            tmp = destination.with_suffix(destination.suffix + ".tmp")
            document = FpkgiDocument(DATA=data)
            _ = tmp.write_text(
                json.dumps(
                    cast(dict[str, object], document.model_dump(mode="json")),
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            _ = tmp.replace(destination)
            exported.append(destination)
            generated_paths.add(destination)

        for managed in self._managed_files():
            if managed in generated_paths:
                continue
            if managed.exists():
                _ = managed.unlink()
        for legacy in self._legacy_files():
            if legacy.exists():
                _ = legacy.unlink()

        return exported

    @override
    def cleanup(self) -> list[Path]:
        removed: list[Path] = []
        for managed in self._managed_files():
            if not managed.exists():
                continue
            _ = managed.unlink()
            removed.append(managed)
        for legacy in self._legacy_files():
            if not legacy.exists():
                continue
            _ = legacy.unlink()
            removed.append(legacy)
        return removed

    def _managed_files(self) -> list[Path]:
        return [self._output_dir / f"{stem}.json" for stem in self._MANAGED_STEMS]

    def _legacy_files(self) -> list[Path]:
        return [self._output_dir / f"{stem}.json" for stem in self._LEGACY_STEMS_TO_CLEAN]
