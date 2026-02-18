from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import ClassVar, cast, final, override
from urllib.parse import parse_qs, urlparse


@final
class HbStoreApiResolver:
    _VERSION_PARTS_REGEX: ClassVar[re.Pattern[str]] = re.compile(r"\d+")
    _STORE_COUNT_ROW_SQL: ClassVar[str] = """
        SELECT number_of_downloads
        FROM homebrews
        WHERE id = ?
        ORDER BY pid DESC
        LIMIT 1
    """
    _CATALOG_COUNT_ROW_SQL: ClassVar[str] = """
        SELECT downloads
        FROM download_counters
        WHERE title_id = ?
        LIMIT 1
    """
    _SEED_COUNTER_SQL: ClassVar[str] = """
        INSERT INTO download_counters (title_id, downloads, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(title_id) DO NOTHING
    """
    _INCREMENT_COUNTER_SQL: ClassVar[str] = """
        UPDATE download_counters
        SET downloads = downloads + 1,
            updated_at = ?
        WHERE title_id = ?
    """
    _COUNTER_SCHEMA_SQL: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS download_counters
        (
            title_id   TEXT PRIMARY KEY,
            downloads  INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """
    _CATALOG_ROW_SQL: ClassVar[str] = """
        SELECT
            COALESCE(content_id, ''),
            COALESCE(app_type, ''),
            COALESCE(version, ''),
            COALESCE(updated_at, '')
        FROM catalog_items
        WHERE title_id = ?
    """
    _CATALOG_BY_CONTENT_ROW_SQL: ClassVar[str] = """
        SELECT
            COALESCE(content_id, ''),
            COALESCE(app_type, '')
        FROM catalog_items
        WHERE content_id = ?
        ORDER BY COALESCE(updated_at, '') DESC
        LIMIT 1
    """
    _PACKAGE_ROW_SQL: ClassVar[str] = """
        SELECT COALESCE(package, '')
        FROM homebrews
        WHERE id = ?
        ORDER BY pid DESC
        LIMIT 1
    """

    def __init__(self, catalog_db_path: Path, store_db_path: Path, base_url: str) -> None:
        self._catalog_db_path = catalog_db_path
        self._store_db_path = store_db_path
        self._base_url = base_url.rstrip("/")

    @staticmethod
    def _normalize_content_id(value: str | None) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _normalize_version(value: str | None) -> str:
        return str(value or "").strip()

    def store_db_hash(self) -> str:
        if not self._store_db_path.exists():
            return ""

        digest = hashlib.md5()
        with self._store_db_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _parse_counter_value(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None
        if isinstance(value, (bytes, bytearray)):
            try:
                return int(bytes(value).decode("utf-8", errors="ignore").strip())
            except ValueError:
                return None
        if isinstance(value, memoryview):
            try:
                return int(value.tobytes().decode("utf-8", errors="ignore").strip())
            except ValueError:
                return None
        return None

    def _catalog_download_count(self, title_id: str) -> int | None:
        if not title_id or not self._catalog_db_path.exists():
            return None
        try:
            with sqlite3.connect(str(self._catalog_db_path)) as conn:
                _ = conn.executescript(self._COUNTER_SCHEMA_SQL)
                row_obj = cast(
                    object,
                    conn.execute(self._CATALOG_COUNT_ROW_SQL, (title_id,)).fetchone(),
                )
        except sqlite3.Error:
            return None

        row = cast(tuple[object] | None, row_obj)
        if row is None:
            return None
        parsed = self._parse_counter_value(row[0])
        if parsed is None:
            return None
        return max(0, parsed)

    def _store_download_count(self, title_id: str) -> int | None:
        if not title_id or not self._store_db_path.exists():
            return None
        try:
            with sqlite3.connect(str(self._store_db_path)) as conn:
                row_obj = cast(
                    object,
                    conn.execute(self._STORE_COUNT_ROW_SQL, (title_id,)).fetchone(),
                )
        except sqlite3.Error:
            return None

        row = cast(tuple[object] | None, row_obj)
        if row is None:
            return None
        parsed = self._parse_counter_value(row[0])
        if parsed is None:
            return None
        return max(0, parsed)

    def _counter_key(
        self, title_id: str, content_id: str | None = None, version: str | None = None
    ) -> str:
        cid = self._normalize_content_id(content_id)
        ver = self._normalize_version(version)
        if cid and ver:
            return f"{cid}@{ver}"
        if cid:
            return cid
        return str(title_id or "").strip()

    def download_count(
        self, title_id: str, content_id: str | None = None, version: str | None = None
    ) -> str:
        key = self._counter_key(title_id, content_id, version)
        if not key:
            return "0"

        from_catalog = self._catalog_download_count(key)
        if from_catalog is not None:
            return str(from_catalog)

        from_store = self._store_download_count(key)
        if from_store is not None:
            return str(from_store)
        return "0"

    def increment_download_count(
        self, title_id: str, content_id: str | None = None, version: str | None = None
    ) -> int:
        key = self._counter_key(title_id, content_id, version)
        if not key or not self._catalog_db_path.exists():
            return 0

        if self._normalize_content_id(content_id):
            seed = 0
        else:
            seed = self._store_download_count(key) or 0
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        try:
            with sqlite3.connect(str(self._catalog_db_path)) as conn:
                _ = conn.executescript(self._COUNTER_SCHEMA_SQL)
                _ = conn.execute(self._SEED_COUNTER_SQL, (key, seed, now, now))
                _ = conn.execute(self._INCREMENT_COUNTER_SQL, (now, key))
                conn.commit()
        except sqlite3.Error:
            return seed

        updated = self._catalog_download_count(key)
        if updated is None:
            return seed
        return updated

    @classmethod
    def _version_key(cls, value: str) -> tuple[int, ...]:
        matches = cast(list[str], cls._VERSION_PARTS_REGEX.findall(str(value or "")))
        parts = [int(item) for item in matches]
        if not parts:
            return tuple()
        while len(parts) > 1 and parts[-1] == 0:
            _ = parts.pop()
        return tuple(parts)

    def _package_url_from_catalog(self, title_id: str) -> str | None:
        if not title_id or not self._catalog_db_path.exists():
            return None

        try:
            with sqlite3.connect(str(self._catalog_db_path)) as conn:
                rows_obj = conn.execute(self._CATALOG_ROW_SQL, (title_id,)).fetchall()
        except sqlite3.Error:
            return None

        rows = cast(list[tuple[str, str, str, str]], rows_obj)
        if not rows:
            return None

        best = max(
            rows,
            key=lambda row: (
                self._version_key(str(row[2] or "")),
                str(row[3] or ""),
                str(row[1] or ""),
                str(row[0] or ""),
            ),
        )

        content_id = str(best[0] or "").strip()
        app_type = str(best[1] or "").strip().lower()
        if not content_id or not app_type:
            return None

        route = f"/pkg/{app_type}/{content_id}.pkg"
        if self._base_url:
            return f"{self._base_url}{route}"
        return route

    def _package_url_from_catalog_content_id(self, content_id: str | None) -> str | None:
        cid = self._normalize_content_id(content_id)
        if not cid or not self._catalog_db_path.exists():
            return None

        try:
            with sqlite3.connect(str(self._catalog_db_path)) as conn:
                row_obj = cast(
                    object,
                    conn.execute(self._CATALOG_BY_CONTENT_ROW_SQL, (cid,)).fetchone(),
                )
        except sqlite3.Error:
            return None

        row = cast(tuple[object, object] | None, row_obj)
        if row is None:
            return None
        content_value = str(row[0] or "").strip()
        app_type = str(row[1] or "").strip().lower()
        if not content_value or not app_type:
            return None
        route = f"/pkg/{app_type}/{content_value}.pkg"
        if self._base_url:
            return f"{self._base_url}{route}"
        return route

    def _package_url_from_store_db(self, title_id: str) -> str | None:
        if not title_id or not self._store_db_path.exists():
            return None

        try:
            with sqlite3.connect(str(self._store_db_path)) as conn:
                row_obj = cast(object, conn.execute(self._PACKAGE_ROW_SQL, (title_id,)).fetchone())
        except sqlite3.Error:
            return None

        row = cast(tuple[object] | None, row_obj)
        if row is None:
            return None

        package_url = str(row[0] or "").strip()
        if not package_url:
            return None
        parsed = urlparse(package_url)
        path = str(parsed.path or "").strip().lower()
        if path in {"download.php", "/download.php"} or path.endswith("/download.php"):
            return None
        return package_url

    def resolve_download_url(self, title_id: str, content_id: str | None = None) -> str | None:
        return (
            self._package_url_from_catalog_content_id(content_id)
            or self._package_url_from_catalog(title_id)
            or self._package_url_from_store_db(title_id)
        )

    def resolve_download_pkg_path(self, title_id: str, content_id: str | None = None) -> str | None:
        destination = self.resolve_download_url(title_id, content_id)
        if not destination:
            return None
        parsed = urlparse(destination)
        path = str(parsed.path or "").strip()
        if not path:
            return None
        normalized = path.lower()
        if not normalized.startswith("/pkg/") or not normalized.endswith(".pkg"):
            return None
        return path


@final
class HbStoreApiServer:
    def __init__(
        self,
        resolver: HbStoreApiResolver,
        logger: logging.Logger,
        host: str = "127.0.0.1",
        port: int = 18191,
    ) -> None:
        self._resolver = resolver
        self._logger = logger
        self._host = host
        self._port = int(port)
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def port(self) -> int:
        server = self._server
        if server is None:
            return self._port
        return int(server.server_address[1])

    def start(self) -> None:
        if self._server is not None:
            return

        handler_cls = self._build_handler()
        server = ThreadingHTTPServer((self._host, self._port), handler_cls)
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, name="hb-store-api-http", daemon=True)
        thread.start()

        self._server = server
        self._thread = thread
        self._logger.debug(
            "HB-Store API started: host: %s, port: %d",
            self._host,
            int(server.server_address[1]),
        )

    def stop(self) -> None:
        server = self._server
        if server is None:
            return

        self._server = None
        thread = self._thread
        self._thread = None

        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
        self._logger.debug("HB-Store API stopped")

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        resolver = self._resolver
        logger = self._logger

        class _Handler(BaseHTTPRequestHandler):
            server_version: str = "HomebrewCdnApi/1.0"
            sys_version: str = ""

            def do_HEAD(self) -> None:
                self._dispatch(send_body=False)

            def do_GET(self) -> None:
                self._dispatch(send_body=True)

            def _dispatch(self, send_body: bool) -> None:
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query, keep_blank_values=True)

                if parsed.path == "/api.php":
                    hash_value = resolver.store_db_hash()
                    self._write_json({"hash": hash_value}, send_body=send_body)
                    return

                if parsed.path == "/download.php":
                    title_id = str(params.get("tid", [""])[0] or "").strip()
                    content_id = str(params.get("cid", [""])[0] or "").strip()
                    version = str(params.get("ver", [""])[0] or "").strip()
                    check = str(params.get("check", [""])[0] or "").strip().lower()
                    if check in {"1", "true", "yes", "on"}:
                        count = resolver.download_count(title_id, content_id, version)
                        self._write_json(
                            {"number_of_downloads": count},
                            send_body=send_body,
                        )
                        return

                    pkg_path = resolver.resolve_download_pkg_path(title_id, content_id)
                    if not pkg_path:
                        self._write_json(
                            {"error": "title_id_not_found"},
                            status=404,
                            send_body=send_body,
                        )
                        return

                    if send_body:
                        _ = resolver.increment_download_count(title_id, content_id, version)

                    # Use internal redirect so clients receive a direct file response (200)
                    # while keeping download counter logic centralized in this endpoint.
                    self.send_response(200)
                    self.send_header("X-Accel-Redirect", pkg_path)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return

                self._write_json({"error": "not_found"}, status=404, send_body=send_body)

            def _write_json(
                self,
                payload: dict[str, str],
                status: int = 200,
                send_body: bool = True,
            ) -> None:
                body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
                    "utf-8"
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if send_body:
                    _ = self.wfile.write(body)

            @override
            def log_message(self, format: str, *args: object) -> None:
                logger.debug("HB-Store API: " + format, *args)

        return _Handler
