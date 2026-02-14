from tabulate import tabulate

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.modules.http_api import ensure_http_api_started
from hb_store_m1.modules.watcher import Watcher
from hb_store_m1.utils.init_utils import InitUtils
from hb_store_m1.utils.log_utils import LogUtils


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
        ("FPGKI_FORMAT_ENABLED", Globals.ENVS.FPGKI_FORMAT_ENABLED),
        ("PKGTOOL_TIMEOUT_SECONDS", Globals.ENVS.PKGTOOL_TIMEOUT_SECONDS),
        (
            "PKGTOOL_VALIDATE_TIMEOUT_SECONDS",
            Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_SECONDS,
        ),
        (
            "PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS",
            Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS,
        ),
        (
            "PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS",
            Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS,
        ),
    ]
    for key, value in items:
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        rows.append([key, value])

    print(tabulate(rows, tablefmt="fancy_outline"))


def main():
    welcome()
    InitUtils.init_all()
    InitUtils.sync_runtime_urls()
    ensure_http_api_started()
    if Globals.ENVS.WATCHER_ENABLED:
        Watcher().start()
    else:
        LogUtils(LogModule.WATCHER).log_info("Watcher is disabled. Skipping...")
