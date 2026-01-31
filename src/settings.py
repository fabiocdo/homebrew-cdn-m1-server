import pathlib

# Constants
DATA_DIR = pathlib.Path("/data")

PKG_DIR = DATA_DIR / "pkg"
MEDIA_DIR = DATA_DIR / "_media"
CACHE_DIR = DATA_DIR / "_cache"
STORE_DB_PATH = DATA_DIR / "store.db"

GAME_DIR = PKG_DIR / "game"
DLC_DIR = PKG_DIR / "dlc"
UPDATE_DIR = PKG_DIR / "update"
APP_DIR = PKG_DIR / "app"

APPTYPE_PATHS = {
    "game": GAME_DIR,
    "dlc": DLC_DIR,
    "update": UPDATE_DIR,
    "app": APP_DIR,
}

INDEX_PATH = DATA_DIR / "index.json"
CACHE_PATH = CACHE_DIR / "index-cache.json"

# Runtime config (set by auto_indexer.py)
BASE_URL = None
LOG_LEVEL = None
PKG_WATCHER_ENABLED = None
AUTO_INDEXER_ENABLED = None
INDEX_JSON_ENABLED = None
AUTO_FORMATTER_ENABLED = None
AUTO_FORMATTER_TEMPLATE = None
AUTO_FORMATTER_MODE = None
AUTO_SORTER_ENABLED = None
PROCESS_WORKERS = None
PERIODIC_SCAN_SECONDS = None

# CLI Arguments
CLI_ARGS = [
    ("--base-url", {"required": True}),
    ("--log-level", {"required": True}),
    ("--pkg-watcher-enabled", {"required": True}),
    ("--auto-indexer-enabled", {"required": True}),
    ("--index-json-enabled", {"required": True}),
    ("--auto-formatter-enabled", {"required": True}),
    ("--auto-sorter-enabled", {"required": True}),
    ("--auto-formatter-template", {"required": True}),
    (
        "--auto-formatter-mode",
        {"required": True, "choices": ["none", "uppercase", "lowercase", "capitalize"]},
    ),
    ("--process-workers", {"required": True}),
    ("--periodic-scan-seconds", {"required": True}),
]
