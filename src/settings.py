import os
import pathlib

# Paths - prioritizing environment variables
DATA_DIR = pathlib.Path(os.getenv("CDN_DATA_DIR", "/home/fabio/dev/homebrew-store-cdn/data"))

PKG_DIR = pathlib.Path(os.getenv("CDN_PKG_DIR", str(DATA_DIR / "pkg")))
ERROR_DIR = pathlib.Path(os.getenv("CDN_ERROR_DIR", str(DATA_DIR / "_errors")))

# Runtime config (set by environment variables)
AUTO_FORMATTER_TEMPLATE = os.getenv("AUTO_FORMATTER_TEMPLATE", "{title} {title_id} {app_type}")
AUTO_FORMATTER_MODE = os.getenv("AUTO_FORMATTER_MODE", "none")
