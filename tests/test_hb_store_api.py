from __future__ import annotations

import hashlib
import http.client
import json
import logging
import sqlite3
from pathlib import Path
from typing import cast

from homebrew_cdn_m1_server.application.hb_store_api import (
    HbStoreApiResolver,
    HbStoreApiServer,
)


def _init_catalog_db(path: Path) -> None:
    schema = (Path(__file__).resolve().parents[1] / "init" / "catalog_db.sql").read_text(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        _ = conn.executescript(schema)
        conn.commit()


def _insert_catalog_row(
    path: Path,
    *,
    content_id: str,
    title_id: str,
    app_type: str,
    version: str,
    updated_at: str,
) -> None:
    with sqlite3.connect(str(path)) as conn:
        _ = conn.execute(
            """
            INSERT INTO catalog_items (
                content_id, title_id, title, app_type, category, version,
                pubtoolinfo, system_ver, release_date, pkg_path,
                pkg_size, pkg_mtime_ns, pkg_fingerprint,
                icon0_path, pic0_path, pic1_path,
                sfo_json, sfo_raw, sfo_hash,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_id,
                title_id,
                "Test title",
                app_type,
                "GD",
                version,
                "c_date=20250101",
                "0x05050000",
                "2025-01-01",
                f"/tmp/{content_id}.pkg",
                100,
                1,
                "fp",
                None,
                None,
                None,
                "{}",
                b"",
                "hash",
                updated_at,
                updated_at,
            ),
        )
        conn.commit()


def _init_store_db(path: Path) -> None:
    schema = (Path(__file__).resolve().parents[1] / "init" / "store_db.sql").read_text("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        _ = conn.executescript(schema)
        conn.commit()


def _insert_store_row(
    path: Path,
    *,
    content_id: str,
    title_id: str,
    package_url: str,
    version: str = "01.00",
    number_of_downloads: int = 0,
) -> None:
    with sqlite3.connect(str(path)) as conn:
        _ = conn.execute(
            """
            INSERT INTO homebrews (
                content_id, id, name, desc, image, package, version,
                picpath, desc_1, desc_2, ReviewStars, Size, Author,
                apptype, pv, main_icon_path, main_menu_pic, releaseddate,
                number_of_downloads, github, video, twitter, md5
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_id,
                title_id,
                "Test title",
                None,
                "http://127.0.0.1/pkg/media/icon0.png",
                package_url,
                version,
                None,
                None,
                None,
                None,
                100,
                None,
                "Game",
                None,
                None,
                None,
                "2025-01-01",
                number_of_downloads,
                None,
                None,
                None,
                None,
            ),
        )
        conn.commit()


def _decode_json_dict(payload: bytes) -> dict[str, str]:
    parsed = cast(object, json.loads(payload.decode("utf-8")))
    assert isinstance(parsed, dict)
    result: dict[str, str] = {}
    for key, value in cast(dict[object, object], parsed).items():
        result[str(key)] = str(value)
    return result


def test_hb_store_api_resolver_given_store_db_when_hash_requested_then_returns_md5(
    temp_workspace: Path,
) -> None:
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _ = store_db.parent.mkdir(parents=True, exist_ok=True)
    _ = store_db.write_bytes(b"abc123")

    resolver = HbStoreApiResolver(
        catalog_db_path=temp_workspace / "data" / "internal" / "catalog" / "catalog.db",
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )

    assert resolver.store_db_hash() == hashlib.md5(b"abc123").hexdigest()


def test_hb_store_api_resolver_given_multiple_versions_when_resolve_then_returns_latest(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)

    _insert_catalog_row(
        catalog_db,
        content_id="UP0000-TEST00000_00-TEST000000000001",
        title_id="CUSA00001",
        app_type="game",
        version="01.09",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    _insert_catalog_row(
        catalog_db,
        content_id="UP0000-TEST00000_00-TEST000000000002",
        title_id="CUSA00001",
        app_type="game",
        version="01.10",
        updated_at="2025-01-01T00:00:00+00:00",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )

    assert (
        resolver.resolve_download_url("CUSA00001")
        == "http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000002.pkg"
    )


def test_hb_store_api_resolver_given_missing_catalog_entry_when_resolve_then_fallback_to_store_db(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    _insert_store_row(
        store_db,
        content_id="UP0000-TEST00000_00-TEST000000000999",
        title_id="CUSA00009",
        package_url="http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000999.pkg",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )

    assert (
        resolver.resolve_download_url("CUSA00009")
        == "http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000999.pkg"
    )
    assert resolver.resolve_download_pkg_path("CUSA00009") == "/pkg/game/UP0000-TEST00000_00-TEST000000000999.pkg"


def test_hb_store_api_resolver_given_base_url_updated_when_resolve_then_uses_latest_value(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    _insert_catalog_row(
        catalog_db,
        content_id="UP0000-TEST00000_00-TEST000000000333",
        title_id="CUSA00333",
        app_type="game",
        version="01.00",
        updated_at="2025-01-03T00:00:00+00:00",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    resolver.set_base_url("https://games.example.com")

    assert (
        resolver.resolve_download_url("CUSA00333")
        == "https://games.example.com/pkg/game/UP0000-TEST00000_00-TEST000000000333.pkg"
    )


def test_hb_store_api_resolver_given_store_self_download_url_when_resolve_then_avoids_loop(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    _insert_store_row(
        store_db,
        content_id="UP0000-TEST00000_00-TEST000000000888",
        title_id="CUSA00088",
        package_url="http://127.0.0.1/download.php?tid=CUSA00088",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )

    assert resolver.resolve_download_url("CUSA00088") is None
    assert resolver.resolve_download_pkg_path("CUSA00088") is None


def test_hb_store_api_server_given_requests_when_called_then_returns_compatible_responses(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    _insert_catalog_row(
        catalog_db,
        content_id="UP0000-TEST00000_00-TEST000000000100",
        title_id="CUSA00100",
        app_type="game",
        version="02.00",
        updated_at="2025-01-02T00:00:00+00:00",
    )
    _insert_store_row(
        store_db,
        content_id="UP0000-TEST00000_00-TEST000000000100",
        title_id="CUSA00100",
        package_url="http://127.0.0.1/download.php?tid=CUSA00100&cid=UP0000-TEST00000_00-TEST000000000100&ver=02.00",
        number_of_downloads=42,
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    server = HbStoreApiServer(
        resolver=resolver,
        logger=logging.getLogger("tests.hb_store_api"),
        host="127.0.0.1",
        port=0,
    )
    server.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)

        conn.request("GET", "/api.php?db_check_hash=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["hash"] == resolver.store_db_hash()

        conn.request("GET", "/download.php?tid=CUSA00100&check=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "42"

        conn.request(
            "GET",
            "/download.php?tid=CUSA00100&cid=UP0000-TEST00000_00-TEST000000000100&ver=02.00",
        )
        response = conn.getresponse()
        _ = response.read()
        assert response.status == 200
        assert (
            response.getheader("X-Accel-Redirect")
            == "/pkg/game/UP0000-TEST00000_00-TEST000000000100.pkg"
        )

        conn.request(
            "GET",
            "/download.php?tid=CUSA00100&cid=UP0000-TEST00000_00-TEST000000000100&ver=02.00&check=true",
        )
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "1"

        conn.request("GET", "/download.php?tid=UNKNOWN")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 404
        payload = _decode_json_dict(body)
        assert payload["error"] == "title_id_not_found"
        conn.close()
    finally:
        server.stop()


def test_hb_store_api_resolver_given_missing_and_invalid_values_when_count_then_defaults_to_zero(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    assert resolver.store_db_hash() == ""
    assert resolver.download_count("") == "0"
    assert resolver.download_count("CUSA00999") == "0"
    assert resolver.increment_download_count("CUSA00999") == 0
    assert resolver.resolve_download_url("CUSA00999") is None
    assert HbStoreApiResolver._version_key("") == tuple()
    assert HbStoreApiResolver._parse_counter_value(memoryview(b" 21 ")) == 21
    assert HbStoreApiResolver._parse_counter_value(bytearray(b"abc")) is None
    assert HbStoreApiResolver._parse_counter_value(True) == 1
    assert HbStoreApiResolver._parse_counter_value(12.9) == 12

    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    with sqlite3.connect(str(store_db)) as conn:
        _ = conn.execute(
            """
            INSERT INTO homebrews (
                content_id, id, name, desc, image, package, version,
                picpath, desc_1, desc_2, ReviewStars, Size, Author,
                apptype, pv, main_icon_path, main_menu_pic, releaseddate,
                number_of_downloads, github, video, twitter, md5
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "UP0000-TEST00000_00-TEST000000009999",
                "CUSA00999",
                "Test title",
                None,
                "http://127.0.0.1/pkg/media/icon0.png",
                "",
                "01.00",
                None,
                None,
                None,
                None,
                "1 B",
                None,
                "Game",
                None,
                None,
                None,
                "2025-01-01",
                "invalid-count",
                None,
                None,
                None,
                None,
            ),
        )
        conn.commit()

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    assert resolver.download_count("CUSA00999") == "0"


def test_hb_store_api_server_given_head_and_restart_when_called_then_stays_stable(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)
    _insert_catalog_row(
        catalog_db,
        content_id="UP0000-TEST00000_00-TEST000000000200",
        title_id="CUSA00200",
        app_type="game",
        version="01.00",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    _insert_store_row(
        store_db,
        content_id="UP0000-TEST00000_00-TEST000000000200",
        title_id="CUSA00200",
        package_url="http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000200.pkg",
    )

    server = HbStoreApiServer(
        resolver=HbStoreApiResolver(
            catalog_db_path=catalog_db,
            store_db_path=store_db,
            base_url="http://127.0.0.1",
        ),
        logger=logging.getLogger("tests.hb_store_api"),
        host="127.0.0.1",
        port=0,
    )
    assert server.port == 0
    server.start()
    running_port = server.port
    assert running_port > 0
    server.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", running_port, timeout=3)
        conn.request(
            "HEAD",
            "/download.php?tid=CUSA00200&cid=UP0000-TEST00000_00-TEST000000000200&ver=01.00",
        )
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert (
            response.getheader("X-Accel-Redirect")
            == "/pkg/game/UP0000-TEST00000_00-TEST000000000200.pkg"
        )
        assert body == b""
        conn.request("HEAD", "/unknown")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 404
        assert body == b""
        conn.close()
    finally:
        server.stop()
        server.stop()


def test_hb_store_api_server_given_same_title_different_content_when_download_then_counts_are_isolated(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)

    cid_one = "UP0000-TEST00000_00-TEST000000000301"
    cid_two = "UP0000-TEST00000_00-TEST000000000302"
    _insert_catalog_row(
        catalog_db,
        content_id=cid_one,
        title_id="CUSA00300",
        app_type="dlc",
        version="01.00",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    _insert_catalog_row(
        catalog_db,
        content_id=cid_two,
        title_id="CUSA00300",
        app_type="dlc",
        version="01.00",
        updated_at="2025-01-01T00:00:00+00:00",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    server = HbStoreApiServer(
        resolver=resolver,
        logger=logging.getLogger("tests.hb_store_api"),
        host="127.0.0.1",
        port=0,
    )
    server.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)

        conn.request("GET", f"/download.php?tid=CUSA00300&cid={cid_one}&ver=01.00")
        response = conn.getresponse()
        _ = response.read()
        assert response.status == 200
        assert response.getheader("X-Accel-Redirect") == f"/pkg/dlc/{cid_one}.pkg"

        conn.request("GET", f"/download.php?tid=CUSA00300&cid={cid_one}&ver=01.00&check=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "1"

        conn.request("GET", f"/download.php?tid=CUSA00300&cid={cid_two}&ver=01.00&check=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "0"

        conn.close()
    finally:
        server.stop()


def test_hb_store_api_server_given_same_content_different_version_when_download_then_counts_are_isolated(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)

    cid = "UP0000-TEST00000_00-TEST000000000401"
    _insert_catalog_row(
        catalog_db,
        content_id=cid,
        title_id="CUSA00400",
        app_type="game",
        version="01.00",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    _insert_catalog_row(
        catalog_db,
        content_id=cid,
        title_id="CUSA00400",
        app_type="update",
        version="02.00",
        updated_at="2025-01-02T00:00:00+00:00",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )
    server = HbStoreApiServer(
        resolver=resolver,
        logger=logging.getLogger("tests.hb_store_api"),
        host="127.0.0.1",
        port=0,
    )
    server.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)

        conn.request("GET", f"/download.php?tid=CUSA00400&cid={cid}&ver=01.00")
        response = conn.getresponse()
        _ = response.read()
        assert response.status == 200
        assert response.getheader("X-Accel-Redirect") == f"/pkg/game/{cid}.pkg"

        conn.request("GET", f"/download.php?tid=CUSA00400&cid={cid}&ver=01.00&check=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "1"

        conn.request("GET", f"/download.php?tid=CUSA00400&cid={cid}&ver=02.00&check=true")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        payload = _decode_json_dict(body)
        assert payload["number_of_downloads"] == "0"

        conn.close()
    finally:
        server.stop()


def test_hb_store_api_resolver_given_tid_only_with_game_and_update_when_resolve_then_prefers_game(
    temp_workspace: Path,
) -> None:
    catalog_db = temp_workspace / "data" / "internal" / "catalog" / "catalog.db"
    store_db = temp_workspace / "data" / "share" / "hb-store" / "store.db"
    _init_catalog_db(catalog_db)
    _init_store_db(store_db)

    cid = "UP0000-TEST00000_00-TEST000000000501"
    _insert_catalog_row(
        catalog_db,
        content_id=cid,
        title_id="CUSA00500",
        app_type="game",
        version="01.00",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    _insert_catalog_row(
        catalog_db,
        content_id=cid,
        title_id="CUSA00500",
        app_type="update",
        version="09.99",
        updated_at="2025-01-02T00:00:00+00:00",
    )

    resolver = HbStoreApiResolver(
        catalog_db_path=catalog_db,
        store_db_path=store_db,
        base_url="http://127.0.0.1",
    )

    assert (
        resolver.resolve_download_url("CUSA00500")
        == f"http://127.0.0.1/pkg/game/{cid}.pkg"
    )
