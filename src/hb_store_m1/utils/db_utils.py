import hashlib
import json
import sqlite3

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.storedb import StoreDB
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.utils.log_utils import LogUtils
from hb_store_m1.utils.url_utils import URLUtils

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
    app_type_raw = str(pkg.app_type or "")
    app_type_label = URLUtils.to_client_app_type(app_type_raw)

    row = {
        "content_id": pkg.content_id,
        "id": pkg.title_id,
        "name": pkg.title,
        "desc": None,
        "image": URLUtils.canonical_media_url(
            pkg.content_id, "icon0", pkg.icon0_png_path
        ),
        "package": URLUtils.canonical_pkg_url(
            pkg.content_id, app_type_raw, pkg.pkg_path
        ),
        "version": pkg.version,
        "picpath": URLUtils.ps4_store_icon_cache_path(pkg.content_id),
        "desc_1": None,
        "desc_2": None,
        "ReviewStars": None,
        "Size": pkg.pkg_path.stat().st_size,
        "Author": None,
        "apptype": app_type_label,
        "pv": None,
        "main_icon_path": (
            URLUtils.canonical_media_url(pkg.content_id, "pic0", pkg.pic0_png_path)
            if pkg.pic0_png_path
            else None
        ),
        "main_menu_pic": (
            URLUtils.canonical_media_url(pkg.content_id, "pic1", pkg.pic1_png_path)
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
    def _ensure_db_initialized() -> None:
        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            InitUtils.init_db()

    @staticmethod
    def _connect() -> sqlite3.Connection:
        return sqlite3.connect(str(Globals.FILES.STORE_DB_FILE_PATH))

    @staticmethod
    def _quote(column: str) -> str:
        return f'"{column}"'

    @staticmethod
    def _build_upsert_sql() -> str:
        columns = [col.value for col in StoreDB.Column]
        conflict_key = StoreDB.Column.CONTENT_ID.value
        insert_cols = ", ".join(DBUtils._quote(col) for col in columns)
        values = ", ".join(f":{col}" for col in columns)
        update_set = ", ".join(
            f"{DBUtils._quote(col)}=excluded.{DBUtils._quote(col)}"
            for col in columns
            if col != conflict_key
        )
        return (
            f"INSERT INTO homebrews ({insert_cols}) "
            f"VALUES ({values}) "
            f"ON CONFLICT({DBUtils._quote(conflict_key)}) DO UPDATE SET {update_set}"
        )

    @staticmethod
    def select_by_content_ids(
        conn: sqlite3.Connection | None,
        content_ids: list[str],
    ) -> Output[list[dict[str, object]]]:
        DBUtils._ensure_db_initialized()

        if not content_ids:
            return Output(Status.OK, [])

        own_conn = conn is None
        if own_conn:
            conn = DBUtils._connect()

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ",".join("?" for _ in content_ids)

        query = f"""
            SELECT content_id, row_md5
            FROM homebrews
            WHERE content_id IN ({placeholders})
        """
        try:
            cursor.execute(query, content_ids)
            rows = [dict(row) for row in cursor.fetchall()]
            return Output(Status.OK, rows)
        finally:
            if own_conn:
                conn.close()

    @staticmethod
    def select_content_ids(conn: sqlite3.Connection | None = None) -> Output[list[str]]:
        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            return Output(Status.NOT_FOUND, [])

        own_conn = conn is None
        if own_conn:
            conn = DBUtils._connect()

        cursor = conn.cursor()
        try:
            cursor.execute("SELECT content_id FROM homebrews")
            return Output(
                Status.OK,
                [row[0] for row in cursor.fetchall() if row and row[0]],
            )
        except Exception as e:
            log.log_error(f"Failed to list content_ids from STORE.DB: {e}")
            return Output(Status.ERROR, [])
        finally:
            if own_conn:
                conn.close()

    @staticmethod
    def upsert(pkgs: list[PKG], conn: sqlite3.Connection | None = None) -> Output:
        DBUtils._ensure_db_initialized()

        if not pkgs:
            return Output(Status.SKIP, "Nothing to upsert")

        own_conn = conn is None
        if own_conn:
            conn = DBUtils._connect()

        content_ids = [pkg.content_id for pkg in pkgs if pkg.content_id]
        existing_output = DBUtils.select_by_content_ids(conn, content_ids)
        existing = {
            row["content_id"]: row["row_md5"] for row in (existing_output.content or [])
        }

        log.log_info(f"Attempting to upsert {len(pkgs)} PKGs in STORE.DB...")

        try:
            conn.execute("BEGIN")
            upsert_sql = DBUtils._build_upsert_sql()

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
            if own_conn:
                conn.close()

    @staticmethod
    def refresh_urls() -> Output:
        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            return Output(Status.NOT_FOUND, "STORE.DB not found")

        conn = DBUtils._connect()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM homebrews").fetchall()
            if not rows:
                return Output(Status.SKIP, "Nothing to refresh")

            conn.execute("BEGIN")
            refreshed = 0
            for row in rows:
                current = dict(row)
                content_id = current.get(StoreDB.Column.CONTENT_ID.value)
                app_type = current.get(StoreDB.Column.APP_TYPE.value)
                app_type_label = URLUtils.to_client_app_type(str(app_type or ""))

                updated = dict(current)
                updated[StoreDB.Column.PACKAGE.value] = URLUtils.canonical_pkg_url(
                    str(content_id or ""),
                    app_type_label,
                    current.get(StoreDB.Column.PACKAGE.value),
                )
                updated[StoreDB.Column.APP_TYPE.value] = app_type_label
                updated[StoreDB.Column.IMAGE.value] = URLUtils.canonical_media_url(
                    str(content_id or ""),
                    "icon0",
                    current.get(StoreDB.Column.IMAGE.value),
                )
                updated[StoreDB.Column.MAIN_ICON_PATH.value] = (
                    URLUtils.canonical_media_url(
                        str(content_id or ""),
                        "pic0",
                        current.get(StoreDB.Column.MAIN_ICON_PATH.value)
                    )
                    if current.get(StoreDB.Column.MAIN_ICON_PATH.value)
                    else None
                )
                updated[StoreDB.Column.PIC_PATH.value] = (
                    URLUtils.ps4_store_icon_cache_path(str(content_id or ""))
                )
                updated[StoreDB.Column.MAIN_MENU_PIC.value] = (
                    URLUtils.canonical_media_url(
                        str(content_id or ""),
                        "pic1",
                        current.get(StoreDB.Column.MAIN_MENU_PIC.value)
                    )
                    if current.get(StoreDB.Column.MAIN_MENU_PIC.value)
                    else None
                )
                updated[StoreDB.Column.ROW_MD5.value] = _generate_row_md5(updated)

                if (
                    updated[StoreDB.Column.PACKAGE.value]
                    == current.get(StoreDB.Column.PACKAGE.value)
                    and updated[StoreDB.Column.IMAGE.value]
                    == current.get(StoreDB.Column.IMAGE.value)
                    and updated[StoreDB.Column.PIC_PATH.value]
                    == current.get(StoreDB.Column.PIC_PATH.value)
                    and updated[StoreDB.Column.MAIN_ICON_PATH.value]
                    == current.get(StoreDB.Column.MAIN_ICON_PATH.value)
                    and updated[StoreDB.Column.MAIN_MENU_PIC.value]
                    == current.get(StoreDB.Column.MAIN_MENU_PIC.value)
                    and updated[StoreDB.Column.APP_TYPE.value]
                    == current.get(StoreDB.Column.APP_TYPE.value)
                    and updated[StoreDB.Column.ROW_MD5.value]
                    == current.get(StoreDB.Column.ROW_MD5.value)
                ):
                    continue

                conn.execute(
                    """
                    UPDATE homebrews
                    SET
                        package = ?,
                        image = ?,
                        picpath = ?,
                        main_icon_path = ?,
                        main_menu_pic = ?,
                        apptype = ?,
                        row_md5 = ?
                    WHERE pid = ?
                    """,
                    (
                        updated[StoreDB.Column.PACKAGE.value],
                        updated[StoreDB.Column.IMAGE.value],
                        updated[StoreDB.Column.PIC_PATH.value],
                        updated[StoreDB.Column.MAIN_ICON_PATH.value],
                        updated[StoreDB.Column.MAIN_MENU_PIC.value],
                        updated[StoreDB.Column.APP_TYPE.value],
                        updated[StoreDB.Column.ROW_MD5.value],
                        current.get("pid"),
                    ),
                )
                refreshed += 1

            conn.commit()
            if refreshed:
                log.log_info(f"Refreshed URLs for {refreshed} rows in STORE.DB")
                return Output(Status.OK, refreshed)
            return Output(Status.SKIP, "URLs already up to date")
        except Exception as e:
            conn.rollback()
            log.log_error(f"Failed to refresh URLs in STORE.DB: {e}")
            return Output(Status.ERROR, 0)
        finally:
            conn.close()

    @staticmethod
    def delete_by_content_ids(content_ids: list[str]) -> Output:

        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH

        if not store_db_file_path.exists():
            return Output(Status.NOT_FOUND, "STORE.DB not found")

        if not content_ids:
            return Output(Status.SKIP, "Nothing to delete")

        conn = DBUtils._connect()
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
