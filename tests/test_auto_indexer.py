import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.modules.auto_indexer import AutoIndexer
from src.models.watcher_models import PlanOutput


class TestAutoIndexer(unittest.TestCase):
    def test_build_entries_maps_urls_and_dates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            pkg_dir = data_dir / "pkg"
            cache_dir = data_dir / "_cache"
            pkg_dir.mkdir(parents=True, exist_ok=True)
            cache_dir.mkdir(parents=True, exist_ok=True)

            pkg_path = pkg_dir / "game" / "sample.pkg"
            pkg_path.parent.mkdir(parents=True, exist_ok=True)
            pkg_path.write_bytes(b"pkg-data")

            icon_path = pkg_dir / "_media" / "icon.png"
            icon_path.parent.mkdir(parents=True, exist_ok=True)
            icon_path.write_bytes(b"png-data")

            with mock.patch.dict(
                os.environ,
                {
                    "DATA_DIR": str(data_dir),
                    "PKG_DIR": str(pkg_dir),
                    "SERVER_IP": "localhost:8080",
                    "ENABLE_TLS": "false",
                    "AUTO_INDEXER_OUTPUT_FORMAT": "json",
                },
                clear=False,
            ):
                indexer = AutoIndexer()
                items = [
                    {
                        "source": str(pkg_path),
                        "pkg": {"planned_path": str(pkg_path), "action": PlanOutput.ALLOW},
                        "icon": {"planned_path": str(icon_path), "action": PlanOutput.ALLOW},
                    }
                ]
                sfo_cache = {
                    str(pkg_path): {
                        "title": "Sample",
                        "content_id": "UP0000-SAMPLE000_00-TEST000000000000",
                        "region": "USA",
                        "version": "01.00",
                        "release_date": "2024-01-31",
                        "app_type": "game",
                    }
                }

                index_data, db_rows = indexer._build_entries(items, sfo_cache)

            self.assertEqual(len(index_data), 1)
            pkg_url = "http://localhost:8080/pkg/game/sample.pkg"
            self.assertIn(pkg_url, index_data)
            payload = index_data[pkg_url]
            self.assertEqual(payload["name"], "Sample")
            self.assertEqual(payload["release"], "01-31-2024")
            self.assertEqual(payload["cover_url"], "http://localhost:8080/pkg/_media/icon.png")

            self.assertIn(pkg_url, db_rows)
            self.assertEqual(db_rows[pkg_url]["apptype"], "Game")

    def test_write_store_db_md5(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "_cache"
            store_dir = Path(tmp_dir) / "store"
            store_dir.mkdir(parents=True, exist_ok=True)
            db_path = store_dir / "store.db"
            db_path.write_bytes(b"test-db")

            with mock.patch.dict(
                os.environ,
                {
                    "CACHE_DIR": str(cache_dir),
                    "STORE_DIR": str(store_dir),
                    "AUTO_INDEXER_OUTPUT_FORMAT": "db",
                },
                clear=False,
            ):
                indexer = AutoIndexer()
                indexer.write_store_db_md5()

            md5_path = cache_dir / "store.db.md5"
            json_path = cache_dir / "store.db.json"
            self.assertTrue(md5_path.exists())
            self.assertEqual(md5_path.read_text(encoding="utf-8"), "1108b4621259e8634b68d2453ef49c74")
            self.assertTrue(json_path.exists())
            self.assertEqual(json_path.read_text(encoding="utf-8"), "{\"hash\": \"1108b4621259e8634b68d2453ef49c74\"}")


if __name__ == "__main__":
    unittest.main()
