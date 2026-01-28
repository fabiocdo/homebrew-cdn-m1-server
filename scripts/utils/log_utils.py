import logging

LOGGER = logging.getLogger()
COLORS = {
    "error": "\033[0;31m",
    "info": "\033[0;37m",
    "default": "\033[0m",
}
MODULE_COLORS = {
    "AUTO_INDEXER": "\033[0;32m",
    "AUTO_MOVER": "\033[0;33m",
    "AUTO_RENAMER": "\033[0;34m",
}
LOG_LEVELS = {
    "created": logging.INFO,
    "modified": logging.INFO,
    "deleted": logging.INFO,
    "error": logging.ERROR,
    "info": logging.INFO,
}
LOG_PREFIXES = {
    "created": "[+]",
    "modified": "[*]",
    "deleted": "[-]",
    "error": "[!]",
    "info": "[·]",
}

if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log(action, message, module=None):
    level = LOG_LEVELS.get(action, logging.INFO)
    prefix = LOG_PREFIXES.get(action, "[*]")
    if module:
        color = MODULE_COLORS[module]
    else:
        color = COLORS.get(action, COLORS["default"])
    module_tag = f"[{module}] " if module else ""
    LOGGER.log(level, f"{color}{prefix} {module_tag}{message}\033[0m")
