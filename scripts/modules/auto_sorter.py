from pathlib import Path
from utils.log_utils import log

def dry_run(pkg, category):
    """Plan move destination based on PKG category."""
    category_map = {
        "ac": "dlc",
        "gc": "game",
        "gd": "game",
        "gp": "update",
        "sd": "save",
    }
    target_folder = category_map.get(category, "_unknown")
    source_path = Path(pkg)
    destination_root = source_path.parent
    return destination_root / target_folder / source_path.name

def run(pkg, category):
    """Move PKG to the category destination folder."""
    target_path = dry_run(pkg, category)
    if target_path is None:
        return None
    source_path = Path(pkg)
    if source_path == target_path:
        return None
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(target_path)
    except Exception:
        log("error", "TODO - AUTO SORTER ERROR", module="AUTO_SORTER")
        return None
    return str(target_path)
