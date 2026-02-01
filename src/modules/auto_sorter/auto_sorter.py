from pathlib import Path
from src.utils import log
from src import settings


class AutoSorter:
    """
    AutoSorter handles PKG organization into category folders.

    It supports dry-run planning and real moving based on PKG category.
    """

    def __init__(self, category_map: dict | None = None, error_path: str | Path | None = None):
        """
        Initialize the sorter.

        :param category_map: Dictionary mapping SFO category to folder name
        :param error_path: Path where conflicting files will be moved
        """
        self.category_map = category_map or {
            "ac": "dlc",
            "gc": "game",
            "gd": "game",
            "gp": "update",
            "sd": "save",
        }
        self.error_path = Path(error_path) if error_path else settings.ERROR_DIR

    def dry_run(self, pkg_path: Path, category: str) -> Path | None:
        """
        Plan the PKG destination path and check for conflicts.

        :param pkg_path: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: Planned Path object or None if conflict
        """
        target_folder = self.category_map.get(category, "_unknown")
        destination_root = pkg_path.parent
        target_path = destination_root / target_folder / pkg_path.name

        if pkg_path != target_path and target_path.exists():
            log("error", "Move conflict detected", message=f"{pkg_path.name} -> {target_path.name} (Target already exists)", module="AUTO_SORTER")
            return None

        return target_path

    def run(self, pkg_path: Path, category: str) -> str | None:
        """
        Move the PKG file to its category folder.

        :param pkg_path: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: New path string if moved, otherwise None
        """
        target_path = self.dry_run(pkg_path, category)

        if not target_path or pkg_path == target_path:
            return None

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            pkg_path.rename(target_path)
        except Exception as e:
            log("error", "Failed to move PKG", message=f"{pkg_path.name} -> {target_path.name}: {str(e)}", module="AUTO_SORTER")
            if self.error_path:
                try:
                    self.error_path.mkdir(parents=True, exist_ok=True)
                    conflict_path = self.error_path / pkg_path.name
                    pkg_path.rename(conflict_path)
                    log("warn", "PKG moved to errors folder due to execution error", message=f"{pkg_path.name} -> {pkg_path.name}", module="AUTO_SORTER")
                except Exception as move_err:
                    log("error", "Failed to move PKG to errors folder", message=f"{pkg_path.name}: {str(move_err)}", module="AUTO_SORTER")
            return None

        return str(target_path)
