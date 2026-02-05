import datetime

from src.models import Global
from src.models.log import LogLevel, LoggingModule, LogColor

LOG_PRIORITY: LogLevel = LogLevel[Global.ENVS.LOG_LEVEL.upper()].priority()

class LogUtils:

    @staticmethod
    def _log(log_level: LogLevel, message=None, module: LoggingModule | None = None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        log_color = log_level.color()

        module_log_tag = "" if not module else f"{module.color()}[{module.name}] {LogColor.RESET}"

        print(f"{timestamp} | {module_log_tag}{log_color}{message}{LogColor.RESET}")

    @staticmethod
    def log_debug(message=None, module: LoggingModule | None = None):
        if LOG_PRIORITY <= LogLevel.DEBUG.priority():
            LogUtils._log(LogLevel.DEBUG, message, module)

    @staticmethod
    def log_info(message=None, module: LoggingModule | None = None):
        if LOG_PRIORITY <= LogLevel.INFO.priority():
            LogUtils._log(LogLevel.INFO, message, module)

    @staticmethod
    def log_warn(message=None, module: LoggingModule | None = None):
        if LOG_PRIORITY <= LogLevel.WARN.priority():
            LogUtils._log(LogLevel.WARN, message, module)

    @staticmethod
    def log_error(message=None, module: LoggingModule | None = None):
        if LOG_PRIORITY <= LogLevel.ERROR.priority():
            LogUtils._log(LogLevel.ERROR, message, module)

log_debug = LogUtils.log_debug
log_info = LogUtils.log_info
log_warn = LogUtils.log_warn
log_error = LogUtils.log_error