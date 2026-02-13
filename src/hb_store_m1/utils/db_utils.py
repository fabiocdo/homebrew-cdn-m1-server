import hashlib
import json
import sqlite3
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.storedb import StoreDB
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.DB_UTIL)


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
    def generate_hash_md5(values_by_column: dict[str, object]) -> str:
        columns = [
            col.value for col in StoreDB.Column if col is not StoreDB.Column.ROW_MD5
        ]
        payload = json.dumps(
            [values_by_column.get(name) for name in columns],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.md5(payload).hexdigest()

    @staticmethod
    def upsert(conn: sqlite3.Connection | None, pkgs: list[PKG]) -> Output:

        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        if not store_db_file_path.exists():
            InitUtils.init_db()

        if not conn:
            conn = sqlite3.connect(Globals.FILES.STORE_DB_FILE_PATH)

        conn.row_factory = sqlite3.Row

        if not pkgs:
            return Output(Status.SKIP, "Nothing to upsert")

        content_ids = [pkg.content_id for pkg in pkgs if pkg.content_id]
        existing_rows_by_id = DBUtils.select_by_content_ids(conn, content_ids).content

        log.log_info(f"Attempting to upsert {len(pkgs)} PKGs in STORE.DB...")
        try:
            conn.execute("BEGIN")

            insert_sql = """
                         INSERT INTO homebrews (content_id, id, name, "desc", image, package, version, picpath, desc_1, desc_2,
                                                ReviewStars, Size, Author, apptype, pv, main_icon_path, main_menu_pic,
                                                releaseddate, number_of_downloads, github, video, twitter, md5, row_md5)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(content_id) DO UPDATE SET
                            id=excluded.id,
                            name=excluded.name,
                            "desc"=excluded."desc",
                            image=excluded.image,
                            package=excluded.package,
                            version=excluded.version,
                            picpath=excluded.picpath,
                            desc_1=excluded.desc_1,
                            desc_2=excluded.desc_2,
                            ReviewStars=excluded.ReviewStars,
                            Size=excluded.Size,
                            Author=excluded.Author,
                            apptype=excluded.apptype,
                            pv=excluded.pv,
                            main_icon_path=excluded.main_icon_path,
                            main_menu_pic=excluded.main_menu_pic,
                            releaseddate=excluded.releaseddate,
                            number_of_downloads=excluded.number_of_downloads,
                            github=excluded.github,
                            video=excluded.video,
                            twitter=excluded.twitter,
                            md5=excluded.md5,
                            row_md5=excluded.row_md5
                         """

            rows_to_insert = []
            skipped_unchanged = 0
            for pkg in pkgs:
                base_url = Globals.ENVS.SERVER_URL.rstrip("/")

                if pkg.pkg_path:
                    try:
                        pkg_rel = (
                            Path(pkg.pkg_path)
                            .resolve()
                            .relative_to(Globals.PATHS.DATA_DIR_PATH)
                        )
                        pkg_url = f"{base_url}/{pkg_rel.as_posix()}"
                    except (OSError, ValueError):
                        pkg_url = str(pkg.pkg_path)
                else:
                    pkg_url = None

                if pkg.icon0_png_path:
                    try:
                        icon_rel = (
                            Path(pkg.icon0_png_path)
                            .resolve()
                            .relative_to(Globals.PATHS.DATA_DIR_PATH)
                        )
                        icon_url = f"{base_url}/{icon_rel.as_posix()}"
                    except (OSError, ValueError):
                        icon_url = str(pkg.icon0_png_path)
                else:
                    icon_url = None

                if pkg.pic0_png_path:
                    try:
                        pic0_rel = (
                            Path(pkg.pic0_png_path)
                            .resolve()
                            .relative_to(Globals.PATHS.DATA_DIR_PATH)
                        )
                        pic0_url = f"{base_url}/{pic0_rel.as_posix()}"
                    except (OSError, ValueError):
                        pic0_url = str(pkg.pic0_png_path)
                else:
                    pic0_url = None

                if pkg.pic1_png_path:
                    try:
                        pic1_rel = (
                            Path(pkg.pic1_png_path)
                            .resolve()
                            .relative_to(Globals.PATHS.DATA_DIR_PATH)
                        )
                        pic1_url = f"{base_url}/{pic1_rel.as_posix()}"
                    except (OSError, ValueError):
                        pic1_url = str(pkg.pic1_png_path)
                else:
                    pic1_url = None
                size = 0
                if pkg.pkg_path and Path(pkg.pkg_path).exists():
                    size = Path(pkg.pkg_path).stat().st_size
                row_values_by_column = {
                    StoreDB.Column.ID.value: pkg.title_id,
                    StoreDB.Column.NAME.value: pkg.title,
                    StoreDB.Column.CONTENT_ID.value: pkg.content_id,
                    StoreDB.Column.DESC.value: None,
                    StoreDB.Column.IMAGE.value: icon_url,
                    StoreDB.Column.PACKAGE.value: pkg_url,
                    StoreDB.Column.VERSION.value: pkg.version,
                    StoreDB.Column.PIC_PATH.value: None,
                    StoreDB.Column.DESC_1.value: None,
                    StoreDB.Column.DESC_2.value: None,
                    StoreDB.Column.REVIEW_STARS.value: None,
                    StoreDB.Column.SIZE.value: size,
                    StoreDB.Column.AUTHOR.value: None,
                    StoreDB.Column.APP_TYPE.value: pkg.app_type,
                    StoreDB.Column.PV.value: None,
                    StoreDB.Column.MAIN_ICON_PATH.value: pic0_url,
                    StoreDB.Column.MAIN_MENU_PIC.value: pic1_url,
                    StoreDB.Column.RELEASEDDATE.value: pkg.release_date,
                    StoreDB.Column.NUMBER_OF_DOWNLOADS.value: 0,
                    StoreDB.Column.GITHUB.value: None,
                    StoreDB.Column.VIDEO.value: None,
                    StoreDB.Column.TWITTER.value: None,
                    StoreDB.Column.MD5.value: None,
                }
                row_md5 = DBUtils.generate_hash_md5(row_values_by_column)
                existing_row_md5 = existing_rows_by_id.get(pkg.content_id)
                if existing_row_md5 == row_md5:
                    skipped_unchanged += 1
                    continue
                rows_to_insert.append(
                    (
                        pkg.content_id,
                        pkg.title_id,
                        pkg.title,
                        None,  # description
                        icon_url,
                        pkg_url,
                        pkg.version,
                        None,  # picpath
                        None,  # desc1
                        None,  # desc2
                        None,  # review stars
                        size,
                        None,  # author
                        pkg.app_type,
                        None,  # pv ?
                        pic0_url,  # main_icon_path
                        pic1_url,  # main_menu_pic
                        pkg.release_date,
                        0,  # number of downloads
                        None,  # github
                        None,  # video
                        None,  # twitter
                        None,  # md5
                        row_md5,
                    )
                )

            if not rows_to_insert:
                conn.rollback()
                log.log_info(
                    f"All PKGs unchanged. Skipped {skipped_unchanged} upserts."
                )
                return Output(Status.SKIP, "Nothing to upsert")

            if rows_to_insert:
                conn.executemany(insert_sql, rows_to_insert)

            conn.commit()

            upserted_pkgs = len(rows_to_insert)
            log.log_info(f"{upserted_pkgs} PKGs upserted successfully")
            if skipped_unchanged:
                log.log_info(f"Skipped {skipped_unchanged} unchanged PKGs")

            return Output(Status.OK, len(rows_to_insert))
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
