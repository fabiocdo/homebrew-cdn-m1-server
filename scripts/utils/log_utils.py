import logging
import os
import threading
import time

LOGGER = logging.getLogger()
LOG_SETTINGS = {
    "debug": {
        "level": logging.DEBUG,
        "color": "\033[0;37m",
        "prefix": "",
    },
    "info": {
        "level": logging.INFO,
        "color": "\033[0m",
        "prefix": "",
    },
    "warn": {
        "level": logging.WARNING,
        "color": "\033[0;33m",
        "prefix": "",
    },
    "error": {
        "level": logging.ERROR,
        "color": "\033[0;31m",
        "prefix": "",
    },
}
MODULE_COLORS = {
    "AUTO_INDEXER": "\033[0;92m",
    "AUTO_SORTER": "\033[0;93m",
    "AUTO_FORMATTER": "\033[1;94m",
}
_thread_state = threading.local()


def set_worker_label(label):
    _thread_state.worker_label = label


def clear_worker_label():
    if hasattr(_thread_state, "worker_label"):
        delattr(_thread_state, "worker_label")


def _module_tag(module):
    if not module:
        return ""
    label = getattr(_thread_state, "worker_label", None)
    display = f"{module}-{label}" if label else module
    base = module.split("-", 1)[0]
    module_color = MODULE_COLORS.get(base, "")
    if module_color:
        return f"{module_color}[{display}]\033[0m "
    return f"[{display}] "
def _resolve_log_level():
    env_level = os.getenv("LOG_LEVEL", "").strip().lower()
    mapping = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    return mapping.get(env_level, logging.INFO)


resolved_level = _resolve_log_level()
if not LOGGER.handlers:
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
else:
    LOGGER.setLevel(resolved_level)


def log(action, message, module=None):
    settings = LOG_SETTINGS.get(action, LOG_SETTINGS["info"])
    level = settings["level"]
    prefix = settings["prefix"]
    color = settings["color"]
    module_tag = _module_tag(module)
    sep = " " if prefix else ""
    message_text = f"{color}{prefix}{sep}{message}\033[0m"
    LOGGER.log(level, f"{module_tag}{message_text}")


def format_log_line(message, module=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    label = getattr(_thread_state, "worker_label", None)
    display = f"{module}-{label}" if module and label else module
    module_tag = f"[{display}] " if display else ""
    return f"{timestamp} {module_tag}{message}"
