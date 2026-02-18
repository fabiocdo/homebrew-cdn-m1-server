from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest

from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem
from homebrew_cdn_m1_server.domain.models.param_sfo_snapshot import ParamSfoSnapshot
from homebrew_cdn_m1_server.domain.models.app_type import AppType
from homebrew_cdn_m1_server.domain.models.content_id import ContentId
from homebrew_cdn_m1_server.application.exporters.fpkgi_json_exporter import FpkgiJsonExporter
from homebrew_cdn_m1_server.application.exporters.store_db_exporter import StoreDbExporter

FPKGI_SCHEMA = Path(__file__).resolve().parents[1] / "init" / "fpkgi.schema.json"


def _read_json_object(path: Path) -> dict[str, object]:
    obj = cast(object, json.loads(path.read_text("utf-8")))
    assert isinstance(obj, dict)
    return cast(dict[str, object], obj)


def _read_data_rows(path: Path) -> dict[str, dict[str, object]]:
    payload = _read_json_object(path)
    data_obj = payload.get("DATA")
    assert isinstance(data_obj, dict)
    data_map = cast(dict[object, object], data_obj)
    rows: dict[str, dict[str, object]] = {}
    for key_obj, value_obj in data_map.items():
        assert isinstance(key_obj, str)
        assert isinstance(value_obj, dict)
        rows[key_obj] = cast(dict[str, object], value_obj)
    return rows


def _item(
    path: Path,
    content_id: str,
    app_type: AppType,
    system_ver: str = "09.00",
    pkg_size: int = 2048,
) -> CatalogItem:
    return CatalogItem(
        content_id=ContentId.parse(content_id),
        title_id="CUSA00001",
        title="My Test",
        app_type=app_type,
        category="GD",
        version="01.00",
        pubtoolinfo="c_date=20250101",
        system_ver=system_ver,
        release_date="2025-01-01",
        pkg_path=path,
        pkg_size=pkg_size,
        pkg_mtime_ns=100,
        pkg_fingerprint="fp",
        icon0_path=path,
        pic0_path=None,
        pic1_path=None,
        sfo=ParamSfoSnapshot(fields={"TITLE": "My Test"}, raw=b"sfo", hash="hash"),
    )


def test_exporters_given_catalog_items_when_export_then_generates_store_db_and_json(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    store_sql = (Path(__file__).resolve().parents[1] / "init" / "store_db.sql")
    store_output = share_dir / "hb-store" / "store.db"

    pkg_path = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000000.pkg"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_path.write_bytes(b"x")

    items = [
        _item(pkg_path, "UP0000-TEST00000_00-TEST000000000000", AppType.GAME),
    ]

    store_exporter = StoreDbExporter(store_output, store_sql, "http://127.0.0.1")
    exported_db = store_exporter.export(items)

    assert exported_db == [store_output]
    conn = sqlite3.connect(str(store_output))
    row_obj = cast(
        object,
        conn.execute("SELECT content_id, apptype, image, package FROM homebrews").fetchone(),
    )
    conn.close()
    row = cast(tuple[str, str, str, str] | None, row_obj)
    assert row == (
        "UP0000-TEST00000_00-TEST000000000000",
        "Game",
        "http://127.0.0.1/pkg/media/UP0000-TEST00000_00-TEST000000000000_icon0.png",
        "http://127.0.0.1/download.php?tid=CUSA00001&cid=UP0000-TEST00000_00-TEST000000000000&ver=01.00",
    )

    json_exporter = FpkgiJsonExporter(
        share_dir / "fpkgi",
        "http://127.0.0.1",
        FPKGI_SCHEMA,
    )
    exported_json = json_exporter.export(items)

    games_json = share_dir / "fpkgi" / "GAMES.json"
    assert games_json in exported_json
    data_rows = _read_data_rows(games_json)
    assert len(data_rows) == 1
    item = data_rows["http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000000.pkg"]
    assert item["cover_url"] == "http://127.0.0.1/pkg/media/UP0000-TEST00000_00-TEST000000000000_icon0.png"


def test_store_db_exporter_given_pkg_sizes_when_export_then_writes_human_readable_size(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    store_sql = (Path(__file__).resolve().parents[1] / "init" / "store_db.sql")
    store_output = share_dir / "hb-store" / "store.db"

    pkg_small = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000101.pkg"
    pkg_small.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_small.write_bytes(b"a")

    pkg_medium = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000102.pkg"
    _ = pkg_medium.write_bytes(b"b")

    pkg_large = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000103.pkg"
    _ = pkg_large.write_bytes(b"c")

    items = [
        _item(
            pkg_small,
            "UP0000-TEST00000_00-TEST000000000101",
            AppType.GAME,
            pkg_size=512,
        ),
        _item(
            pkg_medium,
            "UP0000-TEST00000_00-TEST000000000102",
            AppType.GAME,
            pkg_size=20 * 1024 * 1024,
        ),
        _item(
            pkg_large,
            "UP0000-TEST00000_00-TEST000000000103",
            AppType.GAME,
            pkg_size=3 * 1024 * 1024 * 1024,
        ),
    ]

    exporter = StoreDbExporter(store_output, store_sql, "http://127.0.0.1")
    _ = exporter.export(items)

    conn = sqlite3.connect(str(store_output))
    rows = cast(
        list[tuple[str, str]],
        conn.execute(
            "SELECT content_id, Size FROM homebrews ORDER BY content_id"
        ).fetchall(),
    )
    conn.close()

    assert rows == [
        ("UP0000-TEST00000_00-TEST000000000101", "512 B"),
        ("UP0000-TEST00000_00-TEST000000000102", "20.00 MB"),
        ("UP0000-TEST00000_00-TEST000000000103", "3.00 GB"),
    ]


def test_fpkgi_exporter_given_single_game_when_export_then_generates_all_json_stems(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    pkg_path = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000010.pkg"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_path.write_bytes(b"x")

    items = [
        _item(pkg_path, "UP0000-TEST00000_00-TEST000000000010", AppType.GAME),
    ]

    exporter = FpkgiJsonExporter(
        share_dir / "fpkgi",
        "http://127.0.0.1",
        FPKGI_SCHEMA,
    )
    exported = exporter.export(items)

    expected_stems = (
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
    assert len(exported) == len(expected_stems)
    for stem in expected_stems:
        destination = share_dir / "fpkgi" / f"{stem}.json"
        assert destination in exported
        payload = _read_json_object(destination)
        data_obj = payload.get("DATA")
        assert isinstance(data_obj, dict)
        data_map = cast(dict[object, object], data_obj)
        if stem == "GAMES":
            assert len(data_map) == 1
        else:
            assert data_map == {}


def test_fpkgi_exporter_given_unknown_app_type_when_export_then_routes_to_homebrew(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)
    output_dir = share_dir / "fpkgi"
    output_dir.mkdir(parents=True, exist_ok=True)

    pkg_path = share_dir / "pkg" / "unknown" / "UP0000-TEST00000_00-TEST000000009900.pkg"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_path.write_bytes(b"x")

    legacy_unknown = output_dir / "UNKNOWN.json"
    _ = legacy_unknown.write_text('{"DATA":{"legacy":"value"}}', encoding="utf-8")

    item = _item(pkg_path, "UP0000-TEST00000_00-TEST000000009900", AppType.UNKNOWN)
    exporter = FpkgiJsonExporter(output_dir, "http://127.0.0.1", FPKGI_SCHEMA)
    _ = exporter.export([item])

    homebrew_rows = _read_data_rows(output_dir / "HOMEBREW.json")
    assert (
        "http://127.0.0.1/pkg/unknown/UP0000-TEST00000_00-TEST000000009900.pkg"
        in homebrew_rows
    )
    assert legacy_unknown.exists() is False


def test_fpkgi_exporter_given_system_ver_when_export_then_normalizes_min_fw(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    pkg_a = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000001.pkg"
    pkg_a.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_a.write_bytes(b"a")

    pkg_b = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000002.pkg"
    _ = pkg_b.write_bytes(b"b")

    pkg_c = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000006.pkg"
    _ = pkg_c.write_bytes(b"c")

    items = [
        _item(pkg_a, "UP0000-TEST00000_00-TEST000000000001", AppType.GAME, "0x05050000"),
        _item(pkg_b, "UP0000-TEST00000_00-TEST000000000002", AppType.GAME, ""),
        _item(pkg_c, "UP0000-TEST00000_00-TEST000000000006", AppType.GAME, "09.00.80"),
    ]

    exporter = FpkgiJsonExporter(
        share_dir / "fpkgi",
        "http://127.0.0.1",
        FPKGI_SCHEMA,
    )
    _ = exporter.export(items)

    data = _read_data_rows(share_dir / "fpkgi" / "GAMES.json")
    assert (
        data["http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000001.pkg"][
            "min_fw"
        ]
        == "05.05"
    )
    assert (
        data["http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000002.pkg"][
            "min_fw"
        ]
        == ""
    )
    assert (
        data["http://127.0.0.1/pkg/game/UP0000-TEST00000_00-TEST000000000006.pkg"][
            "min_fw"
        ]
        == "09.00"
    )


def test_fpkgi_exporter_given_pkg_sizes_when_export_then_writes_bytes_only(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    pkg_small = share_dir / "pkg" / "app" / "UP0000-TEST00000_00-TEST000000000003.pkg"
    pkg_small.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_small.write_bytes(b"a")

    pkg_medium = share_dir / "pkg" / "app" / "UP0000-TEST00000_00-TEST000000000004.pkg"
    _ = pkg_medium.write_bytes(b"b")

    pkg_large = share_dir / "pkg" / "app" / "UP0000-TEST00000_00-TEST000000000005.pkg"
    _ = pkg_large.write_bytes(b"c")

    items = [
        _item(
            pkg_small,
            "UP0000-TEST00000_00-TEST000000000003",
            AppType.APP,
            pkg_size=512_000,
        ),
        _item(
            pkg_medium,
            "UP0000-TEST00000_00-TEST000000000004",
            AppType.APP,
            pkg_size=25 * 1024 * 1024,
        ),
        _item(
            pkg_large,
            "UP0000-TEST00000_00-TEST000000000005",
            AppType.APP,
            pkg_size=3 * 1024 * 1024 * 1024,
        ),
    ]

    exporter = FpkgiJsonExporter(
        share_dir / "fpkgi",
        "http://127.0.0.1",
        FPKGI_SCHEMA,
    )
    _ = exporter.export(items)

    data = _read_data_rows(share_dir / "fpkgi" / "APPS.json")

    assert (
        data["http://127.0.0.1/pkg/app/UP0000-TEST00000_00-TEST000000000003.pkg"][
            "size"
        ]
        == "512000"
    )
    assert (
        data["http://127.0.0.1/pkg/app/UP0000-TEST00000_00-TEST000000000004.pkg"][
            "size"
        ]
        == "26214400"
    )
    assert (
        data["http://127.0.0.1/pkg/app/UP0000-TEST00000_00-TEST000000000005.pkg"][
            "size"
        ]
        == "3221225472"
    )


def test_store_db_exporter_given_existing_db_when_cleanup_then_removes_file(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)

    store_sql = Path(__file__).resolve().parents[1] / "init" / "store_db.sql"
    store_output = share_dir / "hb-store" / "store.db"

    pkg_path = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000000.pkg"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_path.write_bytes(b"x")

    item = _item(pkg_path, "UP0000-TEST00000_00-TEST000000000000", AppType.GAME)
    exporter = StoreDbExporter(store_output, store_sql, "http://127.0.0.1")
    _ = exporter.export([item])
    assert store_output.exists() is True

    removed = exporter.cleanup()

    assert removed == [store_output]
    assert store_output.exists() is False


def test_fpkgi_exporter_given_existing_outputs_when_cleanup_then_removes_all_known_json(
    temp_workspace: Path,
):
    output_dir = temp_workspace / "data" / "share" / "fpkgi"
    output_dir.mkdir(parents=True, exist_ok=True)
    managed = [output_dir / "GAMES.json", output_dir / "DLC.json", output_dir / "APPS.json"]
    for path in managed:
        _ = path.write_text('{"DATA":{}}', encoding="utf-8")
    extra = output_dir / "CUSTOM.json"
    _ = extra.write_text("{}", encoding="utf-8")

    exporter = FpkgiJsonExporter(output_dir, "http://127.0.0.1", FPKGI_SCHEMA)
    removed = exporter.cleanup()

    assert set(removed) == set(managed)
    for path in managed:
        assert path.exists() is False
    assert extra.exists() is True


def test_fpkgi_exporter_given_stale_json_when_export_then_resets_managed_file_to_empty_data(
    temp_workspace: Path,
):
    share_dir = temp_workspace / "data" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)
    output_dir = share_dir / "fpkgi"
    output_dir.mkdir(parents=True, exist_ok=True)

    stale = output_dir / "APPS.json"
    _ = stale.write_text('{"DATA":{"old":"data"}}', encoding="utf-8")

    pkg_path = share_dir / "pkg" / "game" / "UP0000-TEST00000_00-TEST000000000099.pkg"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    _ = pkg_path.write_bytes(b"x")
    items = [_item(pkg_path, "UP0000-TEST00000_00-TEST000000000099", AppType.GAME)]

    exporter = FpkgiJsonExporter(output_dir, "http://127.0.0.1", FPKGI_SCHEMA)
    exported = exporter.export(items)

    assert (output_dir / "GAMES.json") in exported
    assert stale.exists() is True
    stale_payload = _read_json_object(stale)
    assert stale_payload == {"DATA": {}}


def test_fpkgi_exporter_given_outdated_schema_when_init_then_raises(temp_workspace: Path):
    output_dir = temp_workspace / "data" / "share" / "fpkgi"
    output_dir.mkdir(parents=True, exist_ok=True)

    bad_schema = temp_workspace / "bad-fpkgi.schema.json"
    _ = bad_schema.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="out of sync"):
        _ = FpkgiJsonExporter(output_dir, "http://127.0.0.1", bad_schema)
