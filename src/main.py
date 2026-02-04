from src.models.globals import Global
from src.models.log_constants import LoggingModule
from src.utils import log_debug, log_info, log_warn, log_error


def welcome():
    print("Welcome! TODO: ADD box")

def init_directories():
    log_debug("Initializing directories...")

    paths = Global.PATHS
    for p in vars(paths).values():
        p.mkdir(parents=True, exist_ok=True)

    log_debug("Directories OK.")

def start():
    welcome()
    log_debug("debug", LoggingModule.AUTO_FORMATTER)
    log_info("info", LoggingModule.AUTO_FORMATTER)
    log_warn("warn", LoggingModule.AUTO_FORMATTER)
    log_error("error", LoggingModule.AUTO_FORMATTER)
    init_directories()

if __name__ == "__main__":
    start()
