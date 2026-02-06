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


def main():
    # welcome()
    init_directories()
    # scan()
    validate(Path("/home/fabio/dev/hb-store-m1/data/shovel.pkg"))

    # Start watcher
