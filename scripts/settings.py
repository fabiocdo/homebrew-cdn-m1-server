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
AUTO_GENERATE_JSON_PERIOD = None
AUTO_PKG_RENAMER_ENABLED = None
AUTO_PKG_RENAMER_TEMPLATE = None
AUTO_PKG_RENAMER_MODE = None
AUTO_PKG_MOVER_ENABLED = None
AUTO_PKG_MOVER_EXCLUDED_DIRS = None

# CLI Arguments
CLI_ARGS = [
    ("--base-url", {"required": True}),
    ("--auto-generate-json-period", {"required": True, "type": float}),
    ("--auto-pkg-renamer-enabled", {"required": True}),
    ("--auto-pkg-renamer-template", {"required": True}),
    (
        "--auto-pkg-renamer-mode",
        {"required": True, "choices": ["none", "uppercase", "lowercase", "capitalize"]},
    ),
    ("--auto-pkg-mover-enabled", {"required": True}),
    ("--auto-pkg-mover-excluded-dirs", {"required": True}),
]
