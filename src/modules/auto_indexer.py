

import json
import os
import sqlite3
import hashlib
from pathlib import Path
from urllib.parse import quote
from src.utils.log_utils import log
from src.models.watcher_models import PlanOutput
from src.utils.index_cache import load_cache, save_cache, DB_SCHEMA_VERSION
from src.models.extraction_result import STORE_APP_TYPE_MAP
from src.utils.url_utils import build_base_url


class AutoIndexer:
    






    def __init__(self):
        





        raw_formats = os.environ["AUTO_INDEXER_OUTPUT_FORMAT"]
        self.output_formats = {
            part.strip().upper()
            for part in raw_formats.split(",")
            if part.strip()
        }

    def run(self, items: list[dict], sfo_cache: dict[str, dict]) -> None:
        









        files_cache, index_cache, meta = load_cache()
        current_index, db_rows = self._build_entries(items, sfo_cache)

        added = {}
        updated = {}
        removed = {}

        for key, payload in current_index.items():
            if key not in index_cache:
                added[key] = payload
            elif index_cache[key] != payload:
                updated[key] = payload

        for key in index_cache:
            if key not in current_index:
                removed[key] = index_cache[key]

        has_changes = bool(added or updated or removed)
        if meta.get("db_schema_version") != DB_SCHEMA_VERSION:
            has_changes = True
            meta["db_schema_version"] = DB_SCHEMA_VERSION

        if "JSON" in self.output_formats:
            if has_changes:
                log("info", "Generating index.json and index-cache.json", module="AUTO_INDEXER")
                index_dir = Path(os.environ["INDEX_DIR"])
                index_dir.mkdir(parents=True, exist_ok=True)
                index_path = index_dir / "index.json"
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump({"DATA": current_index}, f, ensure_ascii=False, indent=2, sort_keys=True)
                log(
                    "info",
                    f"Index update complete (added: {len(added)}, updated: {len(updated)}, removed: {len(removed)})",
                    module="AUTO_INDEXER",
                )
            else:
                log("debug", "Index unchanged. Skipping index.json", module="AUTO_INDEXER")
        else:
            log("debug", "JSON output disabled. Skipping index.json", module="AUTO_INDEXER")

        if "DB" in self.output_formats:
            if has_changes:
                log("info", "Applying DB changes...", module="AUTO_INDEXER")
                self._write_db(added, updated, removed, db_rows)
                self.write_store_db_md5()
            else:
                log("debug", "Index unchanged. Skipping DB update", module="AUTO_INDEXER")

        save_cache(files_cache, current_index, meta)

    def _build_entries(self, items: list[dict], sfo_cache: dict[str, dict]) -> tuple[dict[str, dict], dict[str, dict]]:
        






        data_dir = Path(os.environ["DATA_DIR"])
        pkg_dir = Path(os.environ["PKG_DIR"])
        base_url = build_base_url().rstrip("/")

        index_data = {}
        db_rows = {}
        for item in items:
            if item["pkg"]["action"] == PlanOutput.REJECT:
                continue

            pkg_path = Path(item["pkg"]["planned_path"])
            try:
                pkg_path.relative_to(pkg_dir)
            except ValueError:
                continue

            if not pkg_path.exists():
                pkg_path = Path(item["source"])

            try:
                rel_pkg = pkg_path.relative_to(data_dir).as_posix()
                pkg_url = f"{base_url}/{quote(rel_pkg, safe='/')}"
            except ValueError:
                pkg_url = pkg_path.name

            sfo_payload = sfo_cache.get(item["source"])
            if not sfo_payload:
                continue

            release_date = sfo_payload.get("release_date")
            if release_date and len(release_date) == 10:
                release_date = f"{release_date[5:7]}-{release_date[8:10]}-{release_date[0:4]}"

            cover_url = None
            picpath = None
            if item["icon"]["planned_path"]:
                icon_path = Path(item["icon"]["planned_path"])
                if icon_path.exists():
                    try:
                        rel_icon = icon_path.relative_to(data_dir).as_posix()
                        cover_url = f"{base_url}/{quote(rel_icon, safe='/')}"
                    except ValueError:
                        cover_url = icon_path.name
                    picpath = f"/user/app/NPXS39041/storedata/{icon_path.name}"

            size_bytes = pkg_path.stat().st_size if pkg_path.exists() else 0
            index_data[pkg_url] = {
                "region": sfo_payload.get("region"),
                "name": sfo_payload.get("title"),
                "version": sfo_payload.get("version"),
                "release": release_date,
                "size": size_bytes,
                "min_fw": None,
                "cover_url": cover_url,
            }

            app_type = str(sfo_payload.get("app_type", "")).lower()
            store_app_type = STORE_APP_TYPE_MAP.get(app_type, "Other")

            db_rows[pkg_url] = {
                "id": sfo_payload.get("content_id"),
                "name": sfo_payload.get("title"),
                "desc": None,
                "image": cover_url,
                "package": pkg_url,
                "version": sfo_payload.get("version"),
                "picpath": picpath,
                "desc_1": None,
                "desc_2": None,
                "ReviewStars": None,
                "Size": size_bytes,
                "Author": None,
                "apptype": store_app_type,
                "pv": None,
                "main_icon_path": cover_url,
                "main_menu_pic": None,
                "releaseddate": release_date,
                "number_of_downloads": None,
                "github": None,
                "video": None,
                "twitter": None,
                "md5": None,
            }

        return index_data, db_rows


    def _write_db(
        self,
        added: dict,
        updated: dict,
        removed: dict,
        db_rows: dict[str, dict],
    ) -> None:
        








        db_dir = Path(os.environ["STORE_DIR"])
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "store.db"

        conn = sqlite3.connect(db_path)
        try:
            columns = [
                ("pid", "INTEGER"),
                ("id", "TEXT"),
                ("name", "TEXT"),
                ("desc", "TEXT"),
                ("image", "TEXT"),
                ("package", "TEXT"),
                ("version", "TEXT"),
                ("picpath", "TEXT"),
                ("desc_1", "TEXT"),
                ("desc_2", "TEXT"),
                ("ReviewStars", "REAL"),
                ("Size", "INTEGER"),
                ("Author", "TEXT"),
                ("apptype", "TEXT"),
                ("pv", "TEXT"),
                ("main_icon_path", "TEXT"),
                ("main_menu_pic", "TEXT"),
                ("releaseddate", "TEXT"),
                ("number_of_downloads", "TEXT"),
                ("github", "TEXT"),
                ("video", "TEXT"),
                ("twitter", "TEXT"),
                ("md5", "TEXT"),
            ]

            column_defs = ",\n                  ".join(
                f"\"{name}\" {col_type}"
                for name, col_type in columns
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS homebrews (
                  {column_defs}
                )
                """
            )

            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(homebrews)")
            }
            for name, col_type in columns:
                if name not in existing_cols:
                    conn.execute(f"ALTER TABLE homebrews ADD COLUMN \"{name}\" {col_type}")

            conn.execute("BEGIN")
            conn.execute("DELETE FROM homebrews")

            insert_sql = """
                INSERT INTO homebrews (
                  pid, id, name, "desc", image, package, version, picpath, desc_1, desc_2,
                  ReviewStars, Size, Author, apptype, pv, main_icon_path, main_menu_pic, releaseddate,
                  number_of_downloads, github, video, twitter, md5
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            rows = []
            for idx, pkg_url in enumerate(sorted(db_rows.keys()), start=1):
                row = db_rows.get(pkg_url)
                if not row:
                    continue
                rows.append((
                    idx,
                    row["id"],
                    row["name"],
                    row["desc"],
                    row["image"],
                    row["package"],
                    row["version"],
                    row["picpath"],
                    row["desc_1"],
                    row["desc_2"],
                    row["ReviewStars"],
                    row["Size"],
                    row["Author"],
                    row["apptype"],
                    row["pv"],
                    row["main_icon_path"],
                    row["main_menu_pic"],
                    row["releaseddate"],
                    row["number_of_downloads"],
                    row["github"],
                    row["video"],
                    row["twitter"],
                    row["md5"],
                ))

            if rows:
                conn.executemany(insert_sql, rows)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def write_store_db_md5(self) -> None:
        







        cache_dir = Path(os.environ["CACHE_DIR"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        md5_path = cache_dir / "store.db.md5"
        json_path = cache_dir / "store.db.json"
        db_path = Path(os.environ["STORE_DIR"]) / "store.db"

        if not db_path.exists():
            log("warn", "store.db not found. Skipping store.db.md5", module="AUTO_INDEXER")
            return

        md5 = hashlib.md5()
        with db_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                md5.update(chunk)

        hash_value = md5.hexdigest()
        md5_path.write_text(hash_value, encoding="utf-8")
        json_path.write_text(json.dumps({"hash": hash_value}), encoding="utf-8")
        log(
            "info",
            "Generated store.db checksum files",
            message=f"{db_path} -> {md5_path}, {json_path}",
            module="AUTO_INDEXER",
        )
