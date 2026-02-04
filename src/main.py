from models.globals import GlobalPaths
from models.log_constants import LoggingModule
from utils import log_info, log_debug, log_warn, log_error


def welcome():
    print("Welcome! TODO: ADD box")

def init_directories():
    paths = GlobalPaths()
    for p in vars(paths).values():
        p.mkdir(parents=True, exist_ok=True)

def start():
    welcome()
    log_debug("debug", LoggingModule.AUTO_FORMATTER)
    log_info("info", LoggingModule.AUTO_FORMATTER)
    log_warn("warn", LoggingModule.AUTO_FORMATTER)
    log_error("error", LoggingModule.AUTO_FORMATTER)
    init_directories()

if __name__ == "__main__":
    start()
