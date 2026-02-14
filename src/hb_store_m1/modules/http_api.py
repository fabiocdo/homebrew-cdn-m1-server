import hashlib
import json
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.HTTP_API)

_API_BIND_HOST = "127.0.0.1"
_API_BIND_PORT = 8765
_TRUE_VALUES = {"1", "true", "yes", "on"}
_ALLOWED_APP_TYPES = {"app", "dlc", "game", "save", "update", "unknown"}
_CONTENT_ID_PATTERN = re.compile(
    r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$"
)

_server_lock = threading.Lock()
_server_instance: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


def store_db_hash(db_path: Path | None = None) -> str | None:
    path = db_path or Globals.FILES.STORE_DB_FILE_PATH
    if not path.exists():
        return None

    digest = hashlib.md5()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def lookup_pkg_by_tid(
    tid: str, db_path: Path | None = None
) -> dict[str, object] | None:
    value = (tid or "").strip().upper()
    if not value:
        return None

    path = db_path or Globals.FILES.STORE_DB_FILE_PATH
    if not path.exists():
        return None

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT
                id,
                content_id,
                apptype,
                package,
                number_of_downloads
            FROM homebrews
            WHERE UPPER(id) = ? OR UPPER(content_id) = ?
            ORDER BY CASE WHEN UPPER(id) = ? THEN 0 ELSE 1 END, pid DESC
            LIMIT 1
            """,
            (value, value, value),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        log.log_error(f"Failed to query homebrews by tid={value}: {exc}")
        return None
    finally:
        conn.close()


def pkg_redirect_path(entry: dict[str, object]) -> str | None:
    app_type = str(entry.get("apptype") or "").strip().lower()
    content_id = str(entry.get("content_id") or "").strip().upper()

    if app_type in _ALLOWED_APP_TYPES and _CONTENT_ID_PATTERN.match(content_id):
        return f"/pkg/{app_type}/{content_id}.pkg"

    package_url = str(entry.get("package") or "").strip()
    if not package_url:
        return None

    parsed_path = urlparse(package_url).path or ""
    if parsed_path.startswith("/app/data/pkg/"):
        return parsed_path.replace("/app/data", "", 1)
    pkg_idx = parsed_path.find("/pkg/")
    if pkg_idx >= 0:
        return parsed_path[pkg_idx:]

    return None


def pkg_internal_path(entry: dict[str, object]) -> str | None:
    public_path = pkg_redirect_path(entry)
    if not public_path or not public_path.startswith("/pkg/"):
        return None
    return public_path.replace("/pkg/", "/_internal_pkg/", 1)


def pkg_file_path(entry: dict[str, object]) -> Path | None:
    public_path = pkg_redirect_path(entry)
    if not public_path or not public_path.startswith("/pkg/"):
        return None

    relative_path = Path(public_path.removeprefix("/pkg/"))
    candidate = (Globals.PATHS.PKG_DIR_PATH / relative_path).resolve()
    pkg_root = Globals.PATHS.PKG_DIR_PATH.resolve()
    if candidate != pkg_root and pkg_root not in candidate.parents:
        return None
    return candidate


def increment_downloads_by_content_id(
    content_id: str, db_path: Path | None = None
) -> int | None:
    value = (content_id or "").strip().upper()
    if not value:
        return None

    path = db_path or Globals.FILES.STORE_DB_FILE_PATH
    if not path.exists():
        return None

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE homebrews
            SET number_of_downloads = number_of_downloads + 1
            WHERE UPPER(content_id) = ?
            """,
            (value,),
        )
        if cursor.rowcount <= 0:
            conn.rollback()
            return None

        row = conn.execute(
            "SELECT number_of_downloads FROM homebrews WHERE UPPER(content_id) = ?",
            (value,),
        ).fetchone()
        conn.commit()
        if not row:
            return None
        try:
            return max(0, int(row[0] or 0))
        except (TypeError, ValueError):
            return 0
    except sqlite3.Error as exc:
        log.log_error(f"Failed to increment downloads for content_id={value}: {exc}")
        return None
    finally:
        conn.close()


def _json_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")


class _StoreApiHandler(BaseHTTPRequestHandler):
    server_version = "hb-store-m1-api/1.0"
    protocol_version = "HTTP/1.1"

    def do_HEAD(self):
        self._dispatch(head_only=True)

    def do_GET(self):
        self._dispatch(head_only=False)

    def log_message(self, _format, *_args):
        return

    def _dispatch(self, head_only: bool) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api.php":
            self._handle_api(parsed, head_only)
            return
        if parsed.path == "/download.php":
            self._handle_download(parsed, head_only)
            return

        self._send_json(404, {"error": "not_found"}, head_only)

    def _send_json(
        self, status_code: int, payload: dict[str, object], head_only: bool
    ) -> None:
        body = _json_bytes(payload)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_file(self, file_path: Path, content_type: str, head_only: bool) -> None:
        if not file_path.exists():
            self.send_error(404)
            return

        size = file_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(size))
        self.end_headers()

        if head_only:
            return

        with file_path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                self.wfile.write(chunk)

    def _handle_api(self, parsed, head_only: bool) -> None:
        query = parse_qs(parsed.query, keep_blank_values=True)
        if _is_true((query.get("db_check_hash") or [""])[0]):
            digest = store_db_hash()
            if not digest:
                self._send_json(404, {"error": "store_db_not_found"}, head_only)
                return
            self._send_json(200, {"hash": digest}, head_only)
            return

        json_path = Globals.PATHS.CACHE_DIR_PATH / "store.db.json"
        self._send_file(json_path, "application/json", head_only)

    def _handle_download(self, parsed, head_only: bool) -> None:
        query = parse_qs(parsed.query, keep_blank_values=True)
        tid = (query.get("tid") or [""])[0].strip()
        if not tid:
            self._send_json(400, {"error": "missing_tid"}, head_only)
            return

        entry = lookup_pkg_by_tid(tid)
        if not entry:
            self._send_json(404, {"error": "tid_not_found", "tid": tid}, head_only)
            return

        if _is_true((query.get("check") or [""])[0]):
            count_raw = entry.get("number_of_downloads")
            try:
                count = max(0, int(count_raw or 0))
            except (TypeError, ValueError):
                count = 0
            self._send_json(200, {"number_of_downloads": count}, head_only)
            return

        internal_path = pkg_internal_path(entry)
        file_path = pkg_file_path(entry)
        if not internal_path or not file_path or not file_path.exists():
            self._send_json(404, {"error": "package_not_found", "tid": tid}, head_only)
            return

        if not head_only:
            content_id = str(entry.get("content_id") or "").strip().upper()
            if content_id:
                increment_downloads_by_content_id(content_id)
        self._send_accel_file(internal_path, head_only)

    def _send_accel_file(self, internal_path: str, head_only: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("X-Accel-Redirect", internal_path)
        self.end_headers()
        if not head_only:
            self.wfile.write(b"")


def ensure_http_api_started() -> bool:
    global _server_instance, _server_thread
    with _server_lock:
        if _server_instance is not None:
            return True

        try:
            server = ThreadingHTTPServer(
                (_API_BIND_HOST, _API_BIND_PORT), _StoreApiHandler
            )
        except OSError as exc:
            log.log_error(
                f"Failed to bind HTTP API on {_API_BIND_HOST}:{_API_BIND_PORT}: {exc}"
            )
            return False

        thread = threading.Thread(
            target=server.serve_forever,
            name="hb-store-http-api",
            daemon=True,
        )
        thread.start()
        _server_instance = server
        _server_thread = thread
        log.log_info(f"HTTP API started on {_API_BIND_HOST}:{_API_BIND_PORT}")
        return True
