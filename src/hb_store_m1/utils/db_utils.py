import hashlib
import json
import sqlite3
from urllib.parse import urljoin

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.storedb import StoreDB
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.DB_UTIL)


def _generate_row_md5(values_by_column: dict[str, object]) -> str:
    columns = [col.value for col in StoreDB.Column if col is not StoreDB.Column.ROW_MD5]
    payload = json.dumps(
        [values_by_column.get(name) for name in columns],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def _generate_upsert_params(pkg: PKG) -> dict[str, object]:
    row = {
        "content_id": pkg.content_id,
        "id": pkg.title_id,
        "name": pkg.title,
        "desc": None,
        "image": urljoin(Globals.ENVS.SERVER_URL, str(pkg.icon0_png_path)),
        "package": urljoin(Globals.ENVS.SERVER_URL, str(pkg.pkg_path)),
        "version": pkg.version,
        "picpath": None,
        "desc_1": None,
        "desc_2": None,
        "ReviewStars": None,
        "Size": pkg.pkg_path.stat().st_size,
        "Author": None,
        "apptype": pkg.app_type,
        "pv": None,
        "main_icon_path": (
            urljoin(Globals.ENVS.SERVER_URL, str(pkg.pic0_png_path))
            if pkg.pic0_png_path
            else None
        ),
        "main_menu_pic": (
            urljoin(Globals.ENVS.SERVER_URL, str(pkg.pic1_png_path))
            if pkg.pic1_png_path
            else None
        ),
        "releaseddate": pkg.release_date,
        "number_of_downloads": 0,
        "github": None,
        "video": None,
        "twitter": None,
        "md5": None,
    }

    row["row_md5"] = _generate_row_md5(row)

    return row


class DBUtils:

    @staticmethod
    def select_by_content_ids(
        conn: sqlite3.Connection | None,
        content_ids: list[str],
    ) -> Output[list[dict[str, object]]]:

        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            InitUtils.init_db()

        if not conn:
            conn = sqlite3.connect(Globals.FILES.STORE_DB_FILE_PATH)

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if not content_ids:
            return Output(Status.OK, [])

        placeholders = ",".join("?" for _ in content_ids)

        query = f"""
            SELECT content_id, row_md5
            FROM homebrews
            WHERE content_id IN ({placeholders})
        """

        cursor.execute(query, content_ids)

        rows = [dict(row) for row in cursor.fetchall()]
        return Output(Status.OK, rows)

    @staticmethod
    def upsert(pkgs: list[PKG], conn: sqlite3.Connection | None = None) -> Output:

        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            InitUtils.init_db()

        if not conn:
            conn = sqlite3.connect(str(store_db_file_path))

        if not pkgs:
            return Output(Status.SKIP, "Nothing to upsert")

        content_ids = [pkg.content_id for pkg in pkgs if pkg.content_id]
        existing = {
            row["content_id"]: row["row_md5"]
            for row in DBUtils.select_by_content_ids(conn, content_ids).content
        }

        log.log_info(f"Attempting to upsert {len(pkgs)} PKGs in STORE.DB...")

        try:
            conn.execute("BEGIN")

            COLUMNS = [col.value for col in StoreDB.Column]
            CONFLICT_KEY = StoreDB.Column.CONTENT_ID.value

            def _quote(col: str) -> str:
                return f'"{col}"'

            insert_cols = ", ".join(_quote(c) for c in COLUMNS)
            values = ", ".join(f":{c}" for c in COLUMNS)

            update_set = ", ".join(
                f"{_quote(c)}=excluded.{_quote(c)}"
                for c in COLUMNS
                if c != CONFLICT_KEY
            )

            upsert_sql = f"""
            INSERT INTO homebrews ({insert_cols})
            VALUES ({values})
            ON CONFLICT({_quote(CONFLICT_KEY)}) DO UPDATE SET
            {update_set}
            """

            upsert_params = [
                params
                for pkg in pkgs
                if (params := _generate_upsert_params(pkg)).get("row_md5")
                != existing.get(pkg.content_id)
            ]

            if upsert_params:
                conn.executemany(upsert_sql, upsert_params)

            conn.commit()

            skipped = len(pkgs) - len(upsert_params)

            if skipped:
                log.log_info(f"Skipped {skipped} unchanged PKGs")
                return Output(Status.SKIP, None)

            log.log_info(f"{len(upsert_params)} PKGs upserted successfully")
            return Output(Status.OK, len(upsert_params))

        except Exception as e:
            conn.rollback()
            log.log_error(f"Failed to upsert {len(pkgs)} PKGs in STORE.DB: {e}")
            return Output(Status.ERROR, len(pkgs))

        finally:
            conn.close()

    @staticmethod
    def delete_by_content_ids(content_ids: list[str]) -> Output:

        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH

        if not store_db_file_path.exists():
            return Output(Status.NOT_FOUND, "STORE.DB not found")

        if not content_ids:
            return Output(Status.SKIP, "Nothing to delete")

        conn = sqlite3.connect(str(store_db_file_path))
        log.log_info(f"Attempting to delete {len(content_ids)} PKGs from STORE.DB...")
        try:
            conn.execute("BEGIN")

            before = conn.total_changes
            conn.executemany(
                "DELETE FROM homebrews WHERE content_id = ?",
                [(content_id,) for content_id in content_ids],
            )
            conn.commit()
            deleted = conn.total_changes - before

            log.log_info(f"{deleted} PKGs deleted successfully")
            return Output(Status.OK, deleted)
        except Exception as e:
            conn.rollback()
            log.log_error(f"Failed to delete PKGs from STORE.DB: {e}")
            return Output(Status.ERROR, len(content_ids))
        finally:
            conn.close()


DBUtils = DBUtils()
