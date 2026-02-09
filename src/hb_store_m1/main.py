import json
import os
import sqlite3
from pathlib import Path

from tabulate import tabulate

from hb_store_m1.models.globals import Globals
from hb_store_m1.utils.log_utils import LogUtils
from hb_store_m1.utils.pkg_utils import PkgUtils


def welcome():
    app_banner = f"""
    █ █ █▀▄     █▀▀ ▀█▀ █▀█ █▀▄ █▀▀     █▄█ ▀█ 
    █▀█ █▀▄ ▄▄▄ ▀▀█  █  █ █ █▀▄ █▀▀ ▄▄▄ █ █  █ 
    ▀ ▀ ▀▀      ▀▀▀  ▀  ▀▀▀ ▀ ▀ ▀▀▀     ▀ ▀ ▀▀▀
    v{Globals.ENVS.APP_VERSION}"""
    print(app_banner)
    rows = []
    items = [
        ("SERVER_URL", Globals.ENVS.SERVER_URL),
        ("ENABLE_TLS", Globals.ENVS.ENABLE_TLS),
        ("LOG_LEVEL", Globals.ENVS.LOG_LEVEL),
        ("WATCHER_ENABLED", Globals.ENVS.WATCHER_ENABLED),
        ("WATCHER_PERIODIC_SCAN_SECONDS", Globals.ENVS.WATCHER_PERIODIC_SCAN_SECONDS),
        ("WATCHER_SCAN_BATCH_SIZE", Globals.ENVS.WATCHER_SCAN_BATCH_SIZE),
        ("WATCHER_EXECUTOR_WORKERS", Globals.ENVS.WATCHER_EXECUTOR_WORKERS),
        ("WATCHER_SCAN_WORKERS", Globals.ENVS.WATCHER_SCAN_WORKERS),
        ("WATCHER_ACCESS_LOG_TAIL", Globals.ENVS.WATCHER_ACCESS_LOG_TAIL),
        ("WATCHER_ACCESS_LOG_INTERVAL", Globals.ENVS.WATCHER_ACCESS_LOG_INTERVAL),
        ("AUTO_INDEXER_OUTPUT_FORMAT", Globals.ENVS.AUTO_INDEXER_OUTPUT_FORMAT),
    ]
    for key, value in items:
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        rows.append([key, value])

    print(tabulate(rows, tablefmt="fancy_outline"))


def init_directories():
    LogUtils.log_debug("Initializing directories...")

    paths = Globals.PATHS
    for p in vars(paths).values():
        p.mkdir(parents=True, exist_ok=True)

    LogUtils.log_debug("Directories OK.")


# TODO improve
def init_db():
    store_db = Globals.FILES.STORE_DB_FILE_PATH
    store_db_init_script = Globals.FILES.STORE_DB_INIT_SCRIPT_FILE_PATH

    if store_db.exists():
        LogUtils.log_debug("store.db already exists. Skipping init.")
        return

    if not store_db_init_script.is_file():
        LogUtils.log_warn(
            f"store_db.sql not found at {store_db_init_script}. Skipping store.db init."
        )
        return

    sql = store_db_init_script.read_text("utf-8").strip()
    if not sql:
        LogUtils.log_warn(
            f"store_db.sql at {store_db_init_script} is empty. Skipping store.db init."
        )
        return

    store_db.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(store_db)
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()
        LogUtils.log_info(f"Initialized store.db at {store_db}")
    except sqlite3.Error as exc:
        LogUtils.log_error(f"Failed to initialize store.db: {exc}")


# TODO improve
def init_template_json():
    index_path = Globals.FILES.INDEX_JSON_FILE_PATH
    default_template = Globals.PATHS.INIT_DIR_PATH / "json_template.json"
    template_path = Path(os.getenv("INIT_TEMPLATE_JSON", str(default_template)))

    if index_path.exists():
        LogUtils.log_debug("index.json already exists. Skipping template init.")
        return

    if not template_path.is_file():
        LogUtils.log_warn(
            f"json_template.json not found at {template_path}. Skipping index.json init."
        )
        return

    template_raw = template_path.read_text("utf-8").strip()
    if not template_raw:
        LogUtils.log_warn(
            f"json_template.json at {template_path} is empty. Skipping index.json init."
        )
        return

    try:
        json.loads(template_raw)
    except json.JSONDecodeError as exc:
        LogUtils.log_warn(
            f"json_template.json at {template_path} is invalid JSON: {exc}"
        )
        return

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(template_raw + "\n", encoding="utf-8")
    LogUtils.log_info(f"Initialized index.json at {index_path}")


def main():
    # welcome()
    init_directories()
    init_db()
    init_template_json()
    PkgUtils.scan()
    PkgUtils.extract_pkg_data(
        Path("/home/fabio/dev/hb-store-m1/data/pkg/dlc/twinsen-dlc.pkg")
    )
    print(
        PkgUtils.extract_pkg_data(
            Path("/home/fabio/dev/hb-store-m1/data/pkg/game/stardew_game.pkg")
        )
    )

    # Start watcher
