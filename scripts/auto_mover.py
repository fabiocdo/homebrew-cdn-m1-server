import shutil

import settings
from utils.log_utils import log


def run(pkgs):
    """Move PKGs into apptype folders when enabled."""
    excluded = set()
    if settings.AUTO_MOVER_EXCLUDED_DIRS:
        parts = [part.strip() for part in settings.AUTO_MOVER_EXCLUDED_DIRS.split(",")]
        excluded = {part for part in parts if part}
    for pkg, data in pkgs:
        apptype = data.get("apptype")
        if apptype not in settings.APPTYPE_PATHS:
            continue
        if apptype == "app":
            continue
        if settings.APP_DIR in pkg.parents:
            continue
        if any(part in excluded for part in pkg.parts):
            continue
        target_dir = settings.APPTYPE_PATHS[apptype]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pkg.name

        if pkg.resolve() == target_path.resolve():
            continue
        if target_path.exists():
            log(
                "error",
                f"Target already exists, skipping move: {target_path}",
                module="AUTO_MOVER",
            )
            continue
        try:
            shutil.move(str(pkg), str(target_path))
            log(
                "modified",
                f"Moved: {pkg} -> {target_path}",
                module="AUTO_MOVER",
            )
        except Exception as e:
            log(
                "error",
                f"Error moving PKG to {target_path}: {e}",
                module="AUTO_MOVER",
            )
