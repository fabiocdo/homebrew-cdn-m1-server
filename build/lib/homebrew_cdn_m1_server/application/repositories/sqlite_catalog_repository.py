from __future__ import annotations

from collections.abc import Mapping
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, final

from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.param_sfo_snapshot import ParamSfoSnapshot
from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.content_id import ContentId


@final
class SqliteCatalogRepository:
    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        self._conn = conn
        self._db_path = db_path

    def init_schema(self, schema_sql: str) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        _ = self._conn.executescript(schema_sql)

    @staticmethod
    def _to_row(item: CatalogItem) -> dict[str, object]:
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        return {
            "content_id": item.content_id.value,
            "title_id": item.title_id,
            "title": item.title,
            "app_type": item.app_type.value,
            "category": item.category,
            "version": item.version,
            "pubtoolinfo": item.pubtoolinfo,
            "system_ver": item.system_ver,
            "release_date": item.release_date,
            "pkg_path": str(item.pkg_path),
            "pkg_size": int(item.pkg_size),
            "pkg_mtime_ns": int(item.pkg_mtime_ns),
            "pkg_fingerprint": item.pkg_fingerprint,
            "icon0_path": str(item.icon0_path) if item.icon0_path else None,
            "pic0_path": str(item.pic0_path) if item.pic0_path else None,
            "pic1_path": str(item.pic1_path) if item.pic1_path else None,
            "sfo_json": json.dumps(item.sfo.fields, ensure_ascii=True, sort_keys=True),
            "sfo_raw": item.sfo.raw,
            "sfo_hash": item.sfo.hash,
            "updated_at": now,
            "created_at": now,
        }

    def upsert(self, item: CatalogItem) -> None:
        row = self._to_row(item)
        _ = self._conn.execute(
            """
            INSERT INTO catalog_items (
                content_id, title_id, title, app_type, category, version,
                pubtoolinfo, system_ver, release_date, pkg_path,
                pkg_size, pkg_mtime_ns, pkg_fingerprint,
                icon0_path, pic0_path, pic1_path,
                sfo_json, sfo_raw, sfo_hash,
                created_at, updated_at
            ) VALUES (
                :content_id, :title_id, :title, :app_type, :category, :version,
                :pubtoolinfo, :system_ver, :release_date, :pkg_path,
                :pkg_size, :pkg_mtime_ns, :pkg_fingerprint,
                :icon0_path, :pic0_path, :pic1_path,
                :sfo_json, :sfo_raw, :sfo_hash,
                :created_at, :updated_at
            )
            ON CONFLICT(content_id, app_type, version)
            DO UPDATE SET
                title_id=excluded.title_id,
                title=excluded.title,
                category=excluded.category,
                pubtoolinfo=excluded.pubtoolinfo,
                system_ver=excluded.system_ver,
                release_date=excluded.release_date,
                pkg_path=excluded.pkg_path,
                pkg_size=excluded.pkg_size,
                pkg_mtime_ns=excluded.pkg_mtime_ns,
                pkg_fingerprint=excluded.pkg_fingerprint,
                icon0_path=excluded.icon0_path,
                pic0_path=excluded.pic0_path,
                pic1_path=excluded.pic1_path,
                sfo_json=excluded.sfo_json,
                sfo_raw=excluded.sfo_raw,
                sfo_hash=excluded.sfo_hash,
                updated_at=excluded.updated_at
            """,
            row,
        )

    @staticmethod
    def _row_text(row: Mapping[str, object], key: str) -> str:
        value = row.get(key)
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _row_int(row: Mapping[str, object], key: str) -> int:
        value = row.get(key)
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        if isinstance(value, (bytes, bytearray)):
            try:
                return int(value.decode("utf-8", errors="ignore").strip())
            except ValueError:
                return 0
        if isinstance(value, memoryview):
            try:
                return int(value.tobytes().decode("utf-8", errors="ignore").strip())
            except ValueError:
                return 0
        try:
            return int(str(value))
        except ValueError:
            return 0

    @staticmethod
    def _row_optional_path(row: Mapping[str, object], key: str) -> Path | None:
        value = row.get(key)
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return Path(text)

    @classmethod
    def _parse_row(cls, row: Mapping[str, object]) -> CatalogItem:
        sfo_json_text = cls._row_text(row, "sfo_json") or "{}"
        fields_obj = cast(object, json.loads(sfo_json_text))
        fields: dict[str, str] = {}
        if isinstance(fields_obj, dict):
            for key, value in cast(dict[object, object], fields_obj).items():
                fields[str(key)] = str(value)

        sfo_raw_obj = row.get("sfo_raw")
        sfo_raw: bytes
        if isinstance(sfo_raw_obj, bytes):
            sfo_raw = sfo_raw_obj
        elif isinstance(sfo_raw_obj, bytearray):
            sfo_raw = bytes(sfo_raw_obj)
        elif isinstance(sfo_raw_obj, memoryview):
            sfo_raw = sfo_raw_obj.tobytes()
        else:
            sfo_raw = b""

        content_id_raw = cls._row_text(row, "content_id")
        app_type_raw = cls._row_text(row, "app_type") or "unknown"

        return CatalogItem(
            content_id=ContentId.parse(content_id_raw),
            title_id=cls._row_text(row, "title_id"),
            title=cls._row_text(row, "title"),
            app_type=AppType(app_type_raw),
            category=cls._row_text(row, "category"),
            version=cls._row_text(row, "version"),
            pubtoolinfo=cls._row_text(row, "pubtoolinfo"),
            system_ver=cls._row_text(row, "system_ver"),
            release_date=cls._row_text(row, "release_date"),
            pkg_path=Path(cls._row_text(row, "pkg_path")),
            pkg_size=cls._row_int(row, "pkg_size"),
            pkg_mtime_ns=cls._row_int(row, "pkg_mtime_ns"),
            pkg_fingerprint=cls._row_text(row, "pkg_fingerprint"),
            icon0_path=cls._row_optional_path(row, "icon0_path"),
            pic0_path=cls._row_optional_path(row, "pic0_path"),
            pic1_path=cls._row_optional_path(row, "pic1_path"),
            sfo=ParamSfoSnapshot(
                fields=fields,
                raw=sfo_raw,
                hash=cls._row_text(row, "sfo_hash"),
            ),
            downloads=0,
        )

    def list_items(self) -> list[CatalogItem]:
        self._conn.row_factory = sqlite3.Row
        rows = cast(
            list[sqlite3.Row],
            self._conn.execute(
            """
            SELECT content_id, title_id, title, app_type, category, version,
                   pubtoolinfo, system_ver, release_date, pkg_path,
                   pkg_size, pkg_mtime_ns, pkg_fingerprint,
                   icon0_path, pic0_path, pic1_path,
                   sfo_json, sfo_raw, sfo_hash
            FROM catalog_items
            ORDER BY app_type, content_id, version
            """
            ).fetchall(),
        )

        items: list[CatalogItem] = []
        for row in rows:
            try:
                row_map = cast(dict[str, object], dict(row))
                items.append(self._parse_row(row_map))
            except Exception:
                continue
        return items

    def delete_by_pkg_paths_not_in(self, existing_pkg_paths: set[str]) -> int:
        cursor = self._conn.cursor()
        if not existing_pkg_paths:
            deleted = cursor.execute("DELETE FROM catalog_items").rowcount
            return int(deleted or 0)

        placeholders = ",".join("?" for _ in existing_pkg_paths)
        deleted = cursor.execute(
            f"DELETE FROM catalog_items WHERE pkg_path NOT IN ({placeholders})",
            tuple(existing_pkg_paths),
        ).rowcount
        return int(deleted or 0)
