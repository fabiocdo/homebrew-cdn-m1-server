from src.models.globals import Global
from src.models.log import LoggingModule
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
    init_directories()

if __name__ == "__main__":
    start()
