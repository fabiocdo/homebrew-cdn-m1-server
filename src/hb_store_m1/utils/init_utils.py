import json
import sqlite3

from hb_store_m1.helpers.store_assets_client import StoreAssetClient
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.log_utils import LogUtils


class InitUtils:

    @staticmethod
    def init_directories():
        LogUtils.log_debug("Initializing directories...", LogModule.INIT_UTIL)

        paths = Globals.PATHS
        for p in vars(paths).values():
            p.mkdir(parents=True, exist_ok=True)

        LogUtils.log_info("Directories OK", LogModule.INIT_UTIL)

    @staticmethod
    def init_db():
        store_db_file_path = Globals.FILES.STORE_DB_FILE_PATH
        store_db_init_script = Globals.FILES.STORE_DB_INIT_SCRIPT_FILE_PATH

        LogUtils.log_debug(
            f"Initializing {store_db_file_path.name} ...", LogModule.INIT_UTIL
        )

        if store_db_file_path.exists():
            LogUtils.log_info(
                f"{store_db_file_path.name.upper()} OK",
                LogModule.INIT_UTIL,
            )
            return

        if not store_db_init_script.is_file():
            LogUtils.log_error(
                f"Failed to initialize {store_db_file_path.name}. "
                f"Initialization script {store_db_init_script.name} not found at {store_db_init_script.parent}",
                LogModule.INIT_UTIL,
            )
            return

        sql = store_db_init_script.read_text("utf-8").strip()
        if not sql:
            LogUtils.log_error(
                f"Failed to initialize {store_db_file_path.name}. "
                f"Initialization script {store_db_init_script.name} is empty",
                LogModule.INIT_UTIL,
            )
            return

        store_db_file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(store_db_file_path))
            try:
                conn.executescript(sql)
                conn.commit()
            finally:
                conn.close()
            LogUtils.log_info(
                f"{store_db_file_path.name.upper()} OK", LogModule.INIT_UTIL
            )
        except sqlite3.Error as exc:
            LogUtils.log_error(
                f"Failed to initialize {store_db_file_path.name}: {exc}",
                LogModule.INIT_UTIL,
            )

    @staticmethod
    def init_template_json():
        index_json_file_path = Globals.FILES.INDEX_JSON_FILE_PATH
        index_json_template = Globals.PATHS.INIT_DIR_PATH / "json_template.json"

        LogUtils.log_debug(
            f"Initializing {index_json_file_path.name} ...", LogModule.INIT_UTIL
        )

        if index_json_file_path.exists():
            LogUtils.log_info(
                f"{index_json_file_path.name.upper()} OK",
                LogModule.INIT_UTIL,
            )
            return

        if not index_json_template.is_file():
            LogUtils.log_error(
                f"Failed to initialize {index_json_file_path.name}. "
                f"Initialization script {index_json_template.name} not found at {index_json_template.parent}",
                LogModule.INIT_UTIL,
            )
            return

        template_raw = index_json_template.read_text("utf-8").strip()
        if not template_raw:
            LogUtils.log_error(
                f"Failed to initialize {index_json_file_path.name}. "
                f"Initialization script {index_json_template.name} is empty",
                LogModule.INIT_UTIL,
            )
            return

        try:
            json.loads(template_raw)
            LogUtils.log_info(f"{index_json_file_path.name} OK", LogModule.INIT_UTIL)
        except json.JSONDecodeError as exc:
            LogUtils.log_error(
                f"Failed to initialize {index_json_file_path.name}: {exc}",
                LogModule.INIT_UTIL,
            )
            return

        index_json_file_path.parent.mkdir(parents=True, exist_ok=True)
        index_json_file_path.write_text(template_raw + "\n", encoding="utf-8")
        LogUtils.log_info(
            f"Initialized index.json at {index_json_file_path}", LogModule.INIT_UTIL
        )

    @staticmethod
    def init_assets():
        LogUtils.log_debug("Initializing store assets...", LogModule.INIT_UTIL)

        assets = [
            Globals.FILES.HOMEBREW_ELF_FILE_PATH,
            Globals.FILES.HOMEBREW_ELF_SIG_FILE_PATH,
            Globals.FILES.REMOTE_MD5_FILE_PATH,
        ]

        try:
            downloaded, missing = StoreAssetClient.download_store_assets(assets)
            if missing:
                for asset in missing:
                    LogUtils.log_warn(
                        f"Failed to download asset. Assets {asset.name} not found in repository",
                        LogModule.INIT_UTIL,
                    )
            else:
                LogUtils.log_info("Store assets OK...", LogModule.INIT_UTIL)
        except Exception as e:
            LogUtils.log_error(
                f"Failed to download store assets: {e}", LogModule.INIT_UTIL
            )


InitUtils = InitUtils()
