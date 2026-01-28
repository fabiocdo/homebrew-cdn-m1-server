import logging
import os
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
    "AUTO_MOVER": "\033[0;93m",
    "AUTO_RENAMER": "\033[1;94m",
}
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
    module_color = MODULE_COLORS.get(module, "")
    module_tag = f"{module_color}[{module}]\033[0m " if module else ""
    sep = " " if prefix else ""
    message_text = f"{color}{prefix}{sep}{message}\033[0m"
    LOGGER.log(level, f"{module_tag}{message_text}")


def format_log_line(message, module=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    module_tag = f"[{module}] " if module else ""
    return f"{timestamp} {module_tag}{message}"
