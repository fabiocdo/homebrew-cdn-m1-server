import datetime

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogLevel, LogModule, LogColor

CURRENT_LOG_PRIORITY: LogLevel = LogLevel[Globals.ENVS.LOG_LEVEL.upper()].priority()


class LogUtils:

    @staticmethod
    def _log(log_level: LogLevel, message=None, module: LogModule | None = None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        log_color = log_level.color()

        module_log_tag = (
            "" if not module else f"{module.color()}[{module.name}] {LogColor.RESET}"
        )

        print(f"{timestamp} | {module_log_tag}{log_color}{message}{LogColor.RESET}")

    @staticmethod
    def log_debug(message=None, module: LogModule | None = None):
        if CURRENT_LOG_PRIORITY <= LogLevel.DEBUG.priority():
            LogUtils._log(LogLevel.DEBUG, message, module)

    @staticmethod
    def log_info(message=None, module: LogModule | None = None):
        if CURRENT_LOG_PRIORITY <= LogLevel.INFO.priority():
            LogUtils._log(LogLevel.INFO, message, module)

    @staticmethod
    def log_warn(message=None, module: LogModule | None = None):
        if CURRENT_LOG_PRIORITY <= LogLevel.WARN.priority():
            LogUtils._log(LogLevel.WARN, message, module)

    @staticmethod
    def log_error(message=None, module: LogModule | None = None):
        if CURRENT_LOG_PRIORITY <= LogLevel.ERROR.priority():
            LogUtils._log(LogLevel.ERROR, message, module)


LogUtils = LogUtils()
