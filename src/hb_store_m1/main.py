import sqlite3

from tabulate import tabulate

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.db_utils import DBUtils
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.utils.log_utils import LogUtils
from hb_store_m1.modules.watcher import Watcher


def welcome():
    app_banner = f"""
    █ █ █▀▄     █▀▀ ▀█▀ █▀█ █▀▄ █▀▀     █▄█ ▀█ 
    █▀█ █▀▄ ▄▄▄ ▀▀█  █  █ █ █▀▄ █▀▀ ▄▄▄ █ █  █ 
    ▀ ▀ ▀▀      ▀▀▀  ▀  ▀▀▀ ▀ ▀ ▀▀▀     ▀ ▀ ▀▀▀
    v{Globals.ENVS.APP_VERSION}"""
    print(app_banner)
    rows = []
    items = [
        ("SERVER_IP", Globals.ENVS.SERVER_IP),
        ("SERVER_PORT", Globals.ENVS.SERVER_PORT),
        ("ENABLE_TLS", Globals.ENVS.ENABLE_TLS),
        ("LOG_LEVEL", Globals.ENVS.LOG_LEVEL),
        ("WATCHER_ENABLED", Globals.ENVS.WATCHER_ENABLED),
        ("WATCHER_PERIODIC_SCAN_SECONDS", Globals.ENVS.WATCHER_PERIODIC_SCAN_SECONDS),
        ("FPGKI_FORMAT_ENABLED", Globals.ENVS.FPGKI_FORMAT_ENABLED),
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
    if Globals.ENVS.WATCHER_ENABLED:
        Watcher().start()
    else:
        LogUtils(LogModule.WATCHER).log_info("Watcher is disabled. Skipping...")
