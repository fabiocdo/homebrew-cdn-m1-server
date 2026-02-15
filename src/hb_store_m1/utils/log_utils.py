import datetime

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogLevel, LogModule, LogColor

CURRENT_LOG_PRIORITY: int | None = None


def _current_log_priority() -> int:
    if isinstance(CURRENT_LOG_PRIORITY, int):
        return CURRENT_LOG_PRIORITY
    try:
        return LogLevel[Globals.ENVS.LOG_LEVEL.upper()].priority()
    except KeyError:
        return LogLevel.DEBUG.priority()


class LogUtils:
    def __init__(self, module: LogModule | None = None):
        self._module = module

    @staticmethod
    def _timestamp() -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    def _module_tag(self) -> str:
        if not self._module:
            return ""
        return f"{self._module.color()}[{self._module.name}] {LogColor.RESET}"

    @staticmethod
    def _should_persist_error_log(log_level: LogLevel) -> bool:
        return log_level in (LogLevel.ERROR, LogLevel.WARN)

    def _write_error_log(self, timestamp: str, message: object) -> None:
        try:
            errors_log_file_path = Globals.FILES.ERRORS_LOG_FILE_PATH
            errors_log_file_path.parent.mkdir(parents=True, exist_ok=True)
            module_name = self._module.name if self._module else "APP"
            line = f"{timestamp} | [{module_name}] {message}"
            with errors_log_file_path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError:
            pass

    @staticmethod
    def _can_log(log_level: LogLevel) -> bool:
        return _current_log_priority() <= log_level.priority()

    def _log(self, log_level: LogLevel, message=None):
        timestamp = self._timestamp()
        log_color = log_level.color()
        module_log_tag = self._module_tag()

        print(f"{timestamp} | {module_log_tag}{log_color}{message}{LogColor.RESET}")

        if self._should_persist_error_log(log_level):
            self._write_error_log(timestamp, message)

    def log_debug(self, message=None):
        if self._can_log(LogLevel.DEBUG):
            self._log(LogLevel.DEBUG, message)

    def log_info(self, message=None):
        if self._can_log(LogLevel.INFO):
            self._log(LogLevel.INFO, message)

    def log_warn(self, message=None):
        if self._can_log(LogLevel.WARN):
            self._log(LogLevel.WARN, message)

    def log_error(self, message=None):
        if self._can_log(LogLevel.ERROR):
            self._log(LogLevel.ERROR, message)
