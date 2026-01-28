import logging
import os
import time

LOGGER = logging.getLogger()
COLORS = {
    "debug": "\033[0;90m",
    "info": "\033[0m",
    "warn": "\033[0;33m",
    "error": "\033[0;31m",
}
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}
LOG_PREFIXES = {
    "debug": "[DEBUG]",
    "info": "[INFO]",
    "warn": "[WARN]",
    "error": "[ERROR]",
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
    level = LOG_LEVELS.get(action, logging.INFO)
    prefix = LOG_PREFIXES.get(action, "[*]")
    color = COLORS.get(action, COLORS["info"])
    module_tag = f"[{module}] " if module else ""
    key = (action, module, message)
    now = time.monotonic()
    last = _last_log_times.get(key)
    if last is not None and (now - last) < DEDUPE_WINDOW_SECONDS:
        return
    _last_log_times[key] = now
    LOGGER.log(level, f"{color}{prefix} {module_tag}{message}\033[0m")
