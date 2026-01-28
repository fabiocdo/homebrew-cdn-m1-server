import pathlib

# Constants
DATA_DIR = pathlib.Path("/data")

PKG_DIR = DATA_DIR / "pkg"
MEDIA_DIR = DATA_DIR / "_media"
CACHE_DIR = DATA_DIR / "_cache"

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
PKG_WATCHER_ENABLED = None
AUTO_INDEXER_ENABLED = None
AUTO_RENAMER_ENABLED = None
AUTO_RENAMER_TEMPLATE = None
AUTO_RENAMER_MODE = None
AUTO_MOVER_ENABLED = None
AUTO_MOVER_EXCLUDED_DIRS = None

# CLI Arguments
CLI_ARGS = [
    ("--base-url", {"required": True}),
    ("--pkg-watcher-enabled", {"required": True}),
    ("--auto-indexer-enabled", {"required": True}),
    ("--auto-renamer-enabled", {"required": True}),
    ("--auto-renamer-template", {"required": True}),
    (
        "--auto-renamer-mode",
        {"required": True, "choices": ["none", "uppercase", "lowercase", "capitalize"]},
    ),
    ("--auto-mover-enabled", {"required": True}),
    ("--auto-mover-excluded-dirs", {"required": True}),
]
