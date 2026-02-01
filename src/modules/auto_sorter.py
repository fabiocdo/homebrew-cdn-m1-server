from pathlib import Path
from src.utils import log
from src import settings


class AutoSorter:
    """
    AutoSorter handles PKG organization into category folders.

    It supports dry-run planning and real moving based on PKG category.
    """
    CATEGORY_MAP = {
        "ac": "dlc",
        "gc": "game",
        "gd": "game",
        "gp": "update",
        "sd": "save",
    }

    def __init__(self):
        """
        Initialize the sorter.
        """
        pass

    def dry_run(self, pkg: Path, category: str) -> tuple[Path | None, bool]:
        """
        Plan the PKG destination path and check for conflicts.

        :param pkg: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: Tuple of (Planned Path or None, has_conflict)
        """
        target_folder = self.CATEGORY_MAP.get(category, "_unknown")
        target_path = settings.PKG_DIR / target_folder / pkg.name

        if pkg.parent == target_path.parent:
            log("info", "Skipping sort", message=f"{pkg.name} (PKG is already in correct folder)", module="AUTO_SORTER")
            return None, False

        if target_path.exists():
            log("error", "Failed to move PKG", message=f"{pkg.name} -> {target_path.name} (Target already exists)", module="AUTO_SORTER")
            return None, True

        return target_path, False

    def run(self, pkg: Path, category: str) -> str | None:
        """
        Move the PKG file to its category folder.

        :param pkg: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: New path string if moved, otherwise None
        """
        if not pkg.exists():
            log("error", "PKG file not found", message=f"{pkg}", module="AUTO_SORTER")
            return None

        target_path, has_conflict = self.dry_run(pkg, category)

        if not target_path and not has_conflict:
            return None

        if has_conflict:
            try:
                settings.ERROR_DIR.mkdir(parents=True, exist_ok=True)
                conflict_path = settings.ERROR_DIR / pkg.name
                counter = 1
                while conflict_path.exists():
                    conflict_path = settings.ERROR_DIR / f"{pkg.stem}_{counter}{pkg.suffix}"
                    counter += 1
                pkg.rename(conflict_path)
                log("warn", "PKG moved to errors folder", message=f"{pkg.name} -> {conflict_path.name}", module="AUTO_SORTER")
            except Exception as move_err:
                log("error", "Failed to move PKG to errors folder", message=f"{pkg.name}: {str(move_err)}", module="AUTO_SORTER")
            return None

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            pkg.rename(target_path)
            log("info", "PKG sorted successfully", message=f"{pkg.name} -> {target_path.parent.name}/{target_path.name}", module="AUTO_SORTER")
            return str(target_path)

        except Exception as e:
            try:
                settings.ERROR_DIR.mkdir(parents=True, exist_ok=True)
                conflict_path = settings.ERROR_DIR / pkg.name
                counter = 1
                while conflict_path.exists():
                    conflict_path = settings.ERROR_DIR / f"{pkg.stem}_{counter}{pkg.suffix}"
                    counter += 1
                pkg.rename(conflict_path)
                log("warn", "PKG moved to errors folder due to execution error", message=f"{pkg.name} -> {conflict_path.name}", module="AUTO_SORTER")
            except Exception as move_err:
                log("error", "Failed to move PKG to errors folder", message=f"{pkg.name}: {str(move_err)}", module="AUTO_SORTER")

            return None