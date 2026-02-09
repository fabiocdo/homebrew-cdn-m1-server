from enum import Enum, StrEnum, unique


class LogColor(StrEnum):
    RESET = "\033[0m"
    # Regular
    GRAY = "\033[0;90m"
    WHITE = "\033[0;97m"
    BLUE = "\033[0;34m"
    GREEN = "\033[0;32m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    YELLOW = "\033[0;33m"
    RED = "\033[0;31m"
    # Bright
    BRIGHT_BLUE = "\033[1;94m"
    BRIGHT_GREEN = "\033[1;92m"
    BRIGHT_CYAN = "\033[1;96m"
    BRIGHT_MAGENTA = "\033[1;95m"
    BRIGHT_RED = "\033[1;91m"
    BRIGHT_YELLOW = "\033[1;93m"
    BRIGHT_PURPLE = "\033[38;5;135m"
    BRIGHT_GRAY = "\033[1;90m"


class LogModule(StrEnum):
    DB_UTIL = LogColor.CYAN
    PKG_UTIL = LogColor.MAGENTA
    INIT_UTIL = LogColor.BLUE

    AUTO_INDEXER = LogColor.BRIGHT_GREEN
    AUTO_SORTER = LogColor.BRIGHT_YELLOW
    AUTO_FORMATTER = LogColor.BRIGHT_CYAN
    WATCHER = LogColor.BRIGHT_PURPLE
    WATCHER_PLANNER = LogColor.BRIGHT_RED
    WATCHER_EXECUTOR = LogColor.BRIGHT_GRAY

    def color(self):
        return self.value


class LogLevel(Enum):
    DEBUG = [0, LogColor.GRAY]
    INFO = [1, LogColor.WHITE]
    WARN = [2, LogColor.YELLOW]
    ERROR = [3, LogColor.RED]
    NONE = [4, LogColor.RESET]

    def priority(self):
        return self.value[0]

    def color(self):
        return self.value[1]
