import hashlib
import io
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from hb_store_m1.models.globals import Globals
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.modules import http_api


def _init_store_db(init_paths):
    init_sql = (Path(__file__).resolve().parents[1] / "init" / "store_db.sql").read_text(
        "utf-8"
    )
    (init_paths.INIT_DIR_PATH / "store_db.sql").write_text(init_sql, encoding="utf-8")
    InitUtils.init_db()


def _insert_homebrew(
    *,
    content_id: str = "UP0000-TEST00000_00-TEST000000000000",
    title_id: str = "CUSA00001",
    apptype: str = "Game",
    package: str | None = None,
    version: str = "01.00",
    downloads: int = 0,
):
    pkg_url = package or f"https://cdn.test/pkg/game/{content_id}.pkg"
    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    conn.execute(
        """
        INSERT INTO homebrews (
            content_id, id, name, desc, image, package, version, picpath, desc_1, desc_2,
            ReviewStars, Size, Author, apptype, pv, main_icon_path, main_menu_pic, releaseddate,
            number_of_downloads, github, video, twitter, md5, row_md5
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_id,
            title_id,
            "Test",
            None,
            "https://cdn.test/pkg/_media/icon.png",
            pkg_url,
            version,
            "/user/app/NPXS39041/storedata/icon0.png",
            None,
            None,
            None,
            1,
            None,
            apptype,
            None,
            None,
            None,
            "2024-01-01",
            downloads,
            None,
            None,
            None,
            None,
            "md5",
        ),
    )
    conn.commit()
    conn.close()


def test_given_missing_store_db_when_hash_then_returns_none(temp_globals):
    assert http_api.store_db_hash() is None


def test_given_store_db_file_when_hash_then_returns_md5(init_paths):
    db_path = Globals.FILES.STORE_DB_FILE_PATH
    db_path.write_bytes(b"abc123")

    digest = http_api.store_db_hash()

    assert digest == hashlib.md5(b"abc123").hexdigest()


def test_given_row_when_lookup_by_tid_then_returns_entry(init_paths):
    _init_store_db(init_paths)
    _insert_homebrew()

    row = http_api.lookup_pkg_by_tid("cusa00001")

    assert row is not None
    assert row["id"] == "CUSA00001"
    assert row["content_id"] == "UP0000-TEST00000_00-TEST000000000000"


def test_given_db_error_when_lookup_by_tid_then_returns_none(init_paths, monkeypatch):
    Globals.FILES.STORE_DB_FILE_PATH.write_text("x", encoding="utf-8")

    class _BadConn:
        row_factory = None

        def execute(self, *_args, **_kwargs):
            raise sqlite3.Error("boom")

        def close(self):
            return None

    monkeypatch.setattr(http_api.sqlite3, "connect", lambda *_a, **_k: _BadConn())

    assert http_api.lookup_pkg_by_tid("CUSA99999") is None


def test_given_valid_content_id_and_apptype_when_redirect_then_uses_canonical_path():
    entry = {
        "content_id": "UP0000-TEST00000_00-TEST000000000000",
        "apptype": "Game",
        "package": "https://cdn.test/pkg/anything.pkg",
    }

    path = http_api.pkg_redirect_path(entry)

    assert path == "/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"


def test_given_legacy_package_url_when_redirect_then_normalizes_pkg_prefix():
    entry = {
        "content_id": "invalid",
        "apptype": "Unknown",
        "package": "https://cdn.test/app/data/pkg/dlc/sample.pkg",
    }

    assert http_api.pkg_redirect_path(entry) == "/pkg/dlc/sample.pkg"


def test_given_redirect_path_when_internal_path_then_maps_to_internal_prefix():
    entry = {
        "content_id": "UP0000-TEST00000_00-TEST000000000000",
        "apptype": "Game",
    }

    assert (
        http_api.pkg_internal_path(entry)
        == "/_internal_pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"
    )


def test_given_traversal_pkg_path_when_file_path_then_returns_none():
    entry = {
        "content_id": "invalid",
        "apptype": "Unknown",
        "package": "https://cdn.test/pkg/../../etc/passwd",
    }

    assert http_api.pkg_file_path(entry) is None


def test_given_existing_content_id_when_increment_downloads_then_updates_counter(
    init_paths,
):
    _init_store_db(init_paths)
    _insert_homebrew(downloads=7)

    count = http_api.increment_downloads_by_content_id(
        "UP0000-TEST00000_00-TEST000000000000"
    )

    conn = sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))
    row = conn.execute(
        "SELECT number_of_downloads FROM homebrews WHERE content_id = ?",
        ("UP0000-TEST00000_00-TEST000000000000",),
    ).fetchone()
    conn.close()

    assert count == 8
    assert row[0] == 8


def test_given_missing_content_id_when_increment_downloads_then_returns_none(init_paths):
    _init_store_db(init_paths)
    _insert_homebrew()

    assert (
        http_api.increment_downloads_by_content_id(
            "UP0000-MISSING00_00-AAAAAAAAAAAAAAAA"
        )
        is None
    )


def test_given_payload_when_json_bytes_then_returns_newline_terminated_json():
    payload = {"ok": True, "count": 1}

    body = http_api._json_bytes(payload)

    assert body.endswith(b"\n")
    assert b'"ok": true' in body


class _FakeHandler:
    def __init__(self, path="/"):
        self.path = path
        self.wfile = io.BytesIO()
        self.status_codes = []
        self.headers = []
        self.errors = []
        self.json_calls = []
        self.accel_calls = []
        self.file_calls = []

    def send_response(self, code):
        self.status_codes.append(code)

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        return None

    def send_error(self, code):
        self.errors.append(code)

    def _send_json(self, status_code, payload, head_only):
        self.json_calls.append((status_code, payload, head_only))

    def _send_accel_file(self, internal_path, head_only):
        self.accel_calls.append((internal_path, head_only))

    def _send_file(self, file_path, content_type, head_only):
        self.file_calls.append((file_path, content_type, head_only))

    def _handle_api(self, parsed, head_only):
        self.api_call = (parsed.path, head_only)

    def _handle_download(self, parsed, head_only):
        self.download_call = (parsed.path, head_only)


def test_given_unknown_route_when_dispatch_then_returns_not_found_json():
    fake = _FakeHandler(path="/missing")

    http_api._StoreApiHandler._dispatch(fake, head_only=False)

    assert fake.json_calls == [(404, {"error": "not_found"}, False)]


def test_given_api_and_download_routes_when_dispatch_then_calls_correct_handler():
    api_fake = _FakeHandler(path="/api.php?a=1")
    http_api._StoreApiHandler._dispatch(api_fake, head_only=True)
    assert api_fake.api_call == ("/api.php", True)

    download_fake = _FakeHandler(path="/download.php?tid=x")
    http_api._StoreApiHandler._dispatch(download_fake, head_only=False)
    assert download_fake.download_call == ("/download.php", False)


def test_given_send_json_when_head_only_false_then_writes_body():
    fake = _FakeHandler()

    http_api._StoreApiHandler._send_json(fake, 200, {"ok": True}, head_only=False)

    assert fake.status_codes == [200]
    assert ("Content-Type", "application/json") in fake.headers
    assert fake.wfile.getvalue().endswith(b"\n")


def test_given_send_file_when_missing_then_returns_404_error(tmp_path):
    fake = _FakeHandler()

    http_api._StoreApiHandler._send_file(
        fake,
        tmp_path / "missing.json",
        "application/json",
        head_only=False,
    )

    assert fake.errors == [404]


def test_given_send_file_when_exists_then_streams_bytes(tmp_path):
    fake = _FakeHandler()
    file_path = tmp_path / "ok.json"
    file_path.write_bytes(b'{"ok":1}')

    http_api._StoreApiHandler._send_file(
        fake,
        file_path,
        "application/json",
        head_only=False,
    )

    assert fake.status_codes == [200]
    assert fake.wfile.getvalue() == b'{"ok":1}'


def test_given_api_hash_check_when_store_db_missing_then_returns_404(monkeypatch):
    fake = _FakeHandler()
    parsed = urlparse("/api.php?db_check_hash=true")
    monkeypatch.setattr(http_api, "store_db_hash", lambda: None)

    http_api._StoreApiHandler._handle_api(fake, parsed, head_only=False)

    assert fake.json_calls == [(404, {"error": "store_db_not_found"}, False)]


def test_given_api_hash_check_when_store_db_exists_then_returns_hash(monkeypatch):
    fake = _FakeHandler()
    parsed = urlparse("/api.php?db_check_hash=1")
    monkeypatch.setattr(http_api, "store_db_hash", lambda: "abc")

    http_api._StoreApiHandler._handle_api(fake, parsed, head_only=True)

    assert fake.json_calls == [(200, {"hash": "abc"}, True)]


def test_given_api_without_hash_check_when_handle_api_then_serves_store_db_json():
    fake = _FakeHandler()
    parsed = urlparse("/api.php")

    http_api._StoreApiHandler._handle_api(fake, parsed, head_only=False)

    assert fake.file_calls
    file_path, content_type, head_only = fake.file_calls[0]
    assert file_path.name == "store.db.json"
    assert content_type == "application/json"
    assert head_only is False


def test_given_download_without_tid_when_handle_download_then_returns_400():
    fake = _FakeHandler()
    parsed = urlparse("/download.php")

    http_api._StoreApiHandler._handle_download(fake, parsed, head_only=False)

    assert fake.json_calls == [(400, {"error": "missing_tid"}, False)]


def test_given_download_with_unknown_tid_when_handle_download_then_returns_404(monkeypatch):
    fake = _FakeHandler()
    parsed = urlparse("/download.php?tid=CUSA00001")
    monkeypatch.setattr(http_api, "lookup_pkg_by_tid", lambda _tid: None)

    http_api._StoreApiHandler._handle_download(fake, parsed, head_only=False)

    assert fake.json_calls == [
        (404, {"error": "tid_not_found", "tid": "CUSA00001"}, False)
    ]


def test_given_download_check_when_handle_download_then_returns_counter(monkeypatch):
    fake = _FakeHandler()
    parsed = urlparse("/download.php?tid=CUSA00001&check=true")
    monkeypatch.setattr(
        http_api,
        "lookup_pkg_by_tid",
        lambda _tid: {"number_of_downloads": "9"},
    )

    http_api._StoreApiHandler._handle_download(fake, parsed, head_only=True)

    assert fake.json_calls == [(200, {"number_of_downloads": 9}, True)]


def test_given_download_without_package_when_handle_download_then_returns_404(monkeypatch):
    fake = _FakeHandler()
    parsed = urlparse("/download.php?tid=CUSA00001")
    monkeypatch.setattr(
        http_api,
        "lookup_pkg_by_tid",
        lambda _tid: {"content_id": "UP0000-TEST00000_00-TEST000000000000"},
    )
    monkeypatch.setattr(http_api, "pkg_internal_path", lambda _e: None)
    monkeypatch.setattr(http_api, "pkg_file_path", lambda _e: None)

    http_api._StoreApiHandler._handle_download(fake, parsed, head_only=False)

    assert fake.json_calls == [
        (404, {"error": "package_not_found", "tid": "CUSA00001"}, False)
    ]


def test_given_download_success_when_handle_download_then_increments_and_redirects(
    tmp_path, monkeypatch
):
    fake = _FakeHandler()
    parsed = urlparse("/download.php?tid=CUSA00001")
    package_file = tmp_path / "ok.pkg"
    package_file.write_bytes(b"x")
    entry = {"content_id": "UP0000-TEST00000_00-TEST000000000000"}
    calls = {"incremented": False}

    monkeypatch.setattr(http_api, "lookup_pkg_by_tid", lambda _tid: entry)
    monkeypatch.setattr(http_api, "pkg_internal_path", lambda _e: "/_internal_pkg/game/a.pkg")
    monkeypatch.setattr(http_api, "pkg_file_path", lambda _e: package_file)
    monkeypatch.setattr(
        http_api,
        "increment_downloads_by_content_id",
        lambda _cid: calls.__setitem__("incremented", True) or 1,
    )

    http_api._StoreApiHandler._handle_download(fake, parsed, head_only=False)

    assert calls["incremented"] is True
    assert fake.accel_calls == [("/_internal_pkg/game/a.pkg", False)]


def test_given_send_accel_file_when_called_then_returns_200():
    fake = _FakeHandler()

    http_api._StoreApiHandler._send_accel_file(
        fake,
        "/_internal_pkg/game/item.pkg",
        head_only=False,
    )

    assert fake.status_codes == [200]
    assert ("X-Accel-Redirect", "/_internal_pkg/game/item.pkg") in fake.headers


def test_given_http_api_bind_error_when_start_then_returns_false(monkeypatch):
    http_api._server_instance = None
    http_api._server_thread = None

    def _raise(*_args, **_kwargs):
        raise OSError("bind failed")

    monkeypatch.setattr(http_api, "ThreadingHTTPServer", _raise)

    assert http_api.ensure_http_api_started() is False


def test_given_http_api_not_started_when_start_then_initializes_server(monkeypatch):
    http_api._server_instance = None
    http_api._server_thread = None

    class _FakeServer:
        def __init__(self, *_args, **_kwargs):
            self.started = False

        def serve_forever(self):
            self.started = True

    class _FakeThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(http_api, "ThreadingHTTPServer", _FakeServer)
    monkeypatch.setattr(http_api.threading, "Thread", _FakeThread)

    assert http_api.ensure_http_api_started() is True
    assert http_api.ensure_http_api_started() is True

    http_api._server_instance = None
    http_api._server_thread = None
