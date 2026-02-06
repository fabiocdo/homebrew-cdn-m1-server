import json
import os
import sqlite3
from pathlib import Path

from tabulate import tabulate

from hb_store_m1.models import Global
from hb_store_m1.utils import log_debug, scan, validate, log_info, log_warn, log_error


def welcome():
    app_banner = f"""
    █ █ █▀▄     █▀▀ ▀█▀ █▀█ █▀▄ █▀▀     █▄█ ▀█ 
    █▀█ █▀▄ ▄▄▄ ▀▀█  █  █ █ █▀▄ █▀▀ ▄▄▄ █ █  █ 
    ▀ ▀ ▀▀      ▀▀▀  ▀  ▀▀▀ ▀ ▀ ▀▀▀     ▀ ▀ ▀▀▀
    v{Global.ENVS.APP_VERSION}"""
    print(app_banner)
    rows = []
    items = [
        ("SERVER_URL", Global.ENVS.SERVER_URL),
        ("ENABLE_TLS", Global.ENVS.ENABLE_TLS),
        ("LOG_LEVEL", Global.ENVS.LOG_LEVEL),
        ("WATCHER_ENABLED", Global.ENVS.WATCHER_ENABLED),
        ("WATCHER_PERIODIC_SCAN_SECONDS", Global.ENVS.WATCHER_PERIODIC_SCAN_SECONDS),
        ("WATCHER_SCAN_BATCH_SIZE", Global.ENVS.WATCHER_SCAN_BATCH_SIZE),
        ("WATCHER_EXECUTOR_WORKERS", Global.ENVS.WATCHER_EXECUTOR_WORKERS),
        ("WATCHER_SCAN_WORKERS", Global.ENVS.WATCHER_SCAN_WORKERS),
        ("WATCHER_ACCESS_LOG_TAIL", Global.ENVS.WATCHER_ACCESS_LOG_TAIL),
        ("WATCHER_ACCESS_LOG_INTERVAL", Global.ENVS.WATCHER_ACCESS_LOG_INTERVAL),
        ("AUTO_INDEXER_OUTPUT_FORMAT", Global.ENVS.AUTO_INDEXER_OUTPUT_FORMAT),
    ]
    for key, value in items:
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        rows.append([key, value])

    print(tabulate(rows, tablefmt="fancy_outline"))


def init_directories():
    log_debug("Initializing directories...")

    paths = Global.PATHS
    for p in vars(paths).values():
        p.mkdir(parents=True, exist_ok=True)

    log_debug("Directories OK.")


# TODO improve
def init_db():
    store_db = Global.FILES.STORE_DB_FILE_PATH
    store_db_init_script = Global.FILES.STORE_DB_INIT_SCRIPT_FILE_PATH

    if store_db.exists():
        log_debug("store.db already exists. Skipping init.")
        return

    if not store_db_init_script.is_file():
        log_warn(
            f"store_db.sql not found at {store_db_init_script}. Skipping store.db init."
        )
        return

    sql = store_db_init_script.read_text("utf-8").strip()
    if not sql:
        log_warn(
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
        log_info(f"Initialized store.db at {store_db}")
    except sqlite3.Error as exc:
        log_error(f"Failed to initialize store.db: {exc}")


# TODO improve
def init_template_json():
    index_path = Global.FILES.INDEX_JSON_FILE_PATH
    default_template = Global.PATHS.INIT_DIR_PATH / "json_template.json"
    template_path = Path(os.getenv("INIT_TEMPLATE_JSON", str(default_template)))

    if index_path.exists():
        log_debug("index.json already exists. Skipping template init.")
        return

    if not template_path.is_file():
        log_warn(
            f"json_template.json not found at {template_path}. Skipping index.json init."
        )
        return

    template_raw = template_path.read_text("utf-8").strip()
    if not template_raw:
        log_warn(
            f"json_template.json at {template_path} is empty. Skipping index.json init."
        )
        return

    try:
        json.loads(template_raw)
    except json.JSONDecodeError as exc:
        log_warn(f"json_template.json at {template_path} is invalid JSON: {exc}")
        return

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(template_raw + "\n", encoding="utf-8")
    log_info(f"Initialized index.json at {index_path}")


def main():
    # welcome()
    init_directories()
    init_db()
    init_template_json()
    scan()
    print(validate(Path("/home/fabio/dev/hb-store-m1/data/pkg/game/stardew_game.pkg")))

    # Start watcher
