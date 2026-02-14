import sqlite3

from github import GithubException

from hb_store_m1.helpers.store_assets_client import StoreAssetClient
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Status
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.INIT_UTIL)


class InitUtils:
    @staticmethod
    def init_all():
        InitUtils.init_directories()
        InitUtils.init_db()
        InitUtils.init_assets()

    @staticmethod
    def _read_db_init_sql(db_path, init_script_path) -> str | None:
        if not init_script_path.is_file():
            log.log_error(
                f"Failed to initialize {db_path.name}. "
                f"Initialization script {init_script_path.name} not found at {init_script_path.parent}"
            )
            return None

        sql = init_script_path.read_text("utf-8").strip()
        if not sql:
            log.log_error(
                f"Failed to initialize {db_path.name}. "
                f"Initialization script {init_script_path.name} is empty"
            )
            return None
        return sql

    @staticmethod
    def _assets_to_download():
        return [
            Globals.FILES.HOMEBREW_ELF_FILE_PATH,
            Globals.FILES.HOMEBREW_ELF_SIG_FILE_PATH,
            Globals.FILES.REMOTE_MD5_FILE_PATH,
        ]

    @staticmethod
    def init_directories():
        log.log_debug("Initializing directories...")

        paths = Globals.PATHS
        for p in vars(paths).values():
            p.mkdir(parents=True, exist_ok=True)

        log.log_info("Directories OK")

    @staticmethod
    def init_db():
        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        store_db_init_script = Globals.FILES.STORE_DB_INIT_SCRIPT_FILE_PATH

        log.log_debug(f"Initializing {store_db_file_path.name} ...")

        if store_db_file_path.exists():
            log.log_info(f"{store_db_file_path.name.upper()} OK")
            return

        sql = InitUtils._read_db_init_sql(store_db_file_path, store_db_init_script)
        if not sql:
            return

        store_db_file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(store_db_file_path))
            try:
                conn.executescript(sql)
                conn.commit()
            finally:
                conn.close()
            log.log_info(f"{store_db_file_path.name.upper()} OK")
        except sqlite3.Error as exc:
            log.log_error(f"Failed to initialize {store_db_file_path.name}: {exc}")

    @staticmethod
    def init_assets():
        log.log_debug("Initializing store assets...")

        assets = InitUtils._assets_to_download()

        try:
            downloaded, missing = StoreAssetClient.download_store_assets(assets)
            if missing:
                for asset in missing:
                    log.log_warn(
                        f"Failed to download asset. Assets {asset.name} not found in repository"
                    )
            else:
                log.log_info("Store assets OK...")
        except GithubException as e:
            message = (getattr(e, "data", {}) or {}).get("message", str(e))
            log.log_error(f"Failed to download store assets: {message}")
        except Exception as e:
            log.log_error(f"Failed to download store assets: {e}")

    @staticmethod
    def sync_runtime_urls():
        from hb_store_m1.utils.db_utils import DBUtils
        from hb_store_m1.utils.fpkgi_utils import FPKGIUtils

        db_result = DBUtils.refresh_urls()
        if db_result.status is Status.ERROR:
            log.log_warn("Failed to refresh STORE.DB URLs at startup")

        fpkgi_result = FPKGIUtils.refresh_urls()
        if fpkgi_result.status is Status.ERROR:
            log.log_warn("Failed to refresh FPKGI JSON URLs at startup")


InitUtils = InitUtils()
