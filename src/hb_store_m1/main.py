from pathlib import Path

from tabulate import tabulate

from hb_store_m1.models.globals import Globals
from hb_store_m1.utils.cache_utils import CacheUtils
from hb_store_m1.utils.db_utils import DBUtils
from hb_store_m1.utils.init_utils import InitUtils
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


def main():
    # welcome()
    InitUtils.init_directories()
    InitUtils.init_db()
    InitUtils.init_template_json()
    InitUtils.init_assets()
    PkgUtils.scan()
    pkg0 = PkgUtils.extract_pkg_data(
        Path("/home/fabio/dev/hb-store-m1/data/pkg/dlc/twinsen-dlc.pkg")
    ).content
    pkg1 = PkgUtils.extract_pkg_data(
        Path("/home/fabio/dev/hb-store-m1/data/pkg/game/stardew_game.pkg")
    ).content

    DBUtils.upsert([pkg0, pkg1])

    print(CacheUtils.read_store_db_cache())

    # Start watcher
