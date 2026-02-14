import datetime

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogLevel, LogModule, LogColor

CURRENT_LOG_PRIORITY: LogLevel = LogLevel[Globals.ENVS.LOG_LEVEL.upper()].priority()


class LogUtils:
    def __init__(self, module: LogModule | None = None):
        self._module = module

    def _log(self, log_level: LogLevel, message=None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        log_color = log_level.color()
        module_log_tag = (
            ""
            if not self._module
            else f"{self._module.color()}[{self._module.name}] {LogColor.RESET}"
        )

        print(f"{timestamp} | {module_log_tag}{log_color}{message}{LogColor.RESET}")

        if log_level is LogLevel.ERROR:
            try:
                errors_log_file_path = Globals.FILES.ERRORS_LOG_FILE_PATH
                line = f"{timestamp} | [{self._module.name}] {message}"
                errors_log_file_path.open("a", encoding="utf-8").write(line + "\n")
            except OSError:
                pass

    def log_debug(self, message=None):
        if CURRENT_LOG_PRIORITY <= LogLevel.DEBUG.priority():
            self._log(LogLevel.DEBUG, message)

    def log_info(self, message=None):
        if CURRENT_LOG_PRIORITY <= LogLevel.INFO.priority():
            self._log(LogLevel.INFO, message)

    def log_warn(self, message=None):
        if CURRENT_LOG_PRIORITY <= LogLevel.WARN.priority():
            self._log(LogLevel.WARN, message)

    def log_error(self, message=None):
        if CURRENT_LOG_PRIORITY <= LogLevel.ERROR.priority():
            self._log(LogLevel.ERROR, message)
