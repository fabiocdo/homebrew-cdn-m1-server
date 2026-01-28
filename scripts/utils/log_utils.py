import logging
import os
import time

LOGGER = logging.getLogger()
LOG_SETTINGS = {
    "debug": {
        "level": logging.DEBUG,
        "color": "\033[0;90m",
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
DEDUPE_WINDOW_SECONDS = 2.0
_last_log_times = {}

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
    module_tag = f"[{module}] " if module else ""
    key = (action, module, message)
    now = time.monotonic()
    last = _last_log_times.get(key)
    if last is not None and (now - last) < DEDUPE_WINDOW_SECONDS:
        return
    _last_log_times[key] = now
    sep = " " if prefix else ""
    LOGGER.log(level, f"{color}{prefix}{sep}{module_tag}{message}\033[0m")
