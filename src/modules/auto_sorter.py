import os
from pathlib import Path
from enum import Enum
from src.utils import log


class AutoSorter:
    """
    AutoSorter handles PKG organization into category folders.

    It supports dry-run planning and real moving based on PKG category.
    """

    class PlanResult(Enum):
        """Enumeration of dry-run planning results."""
        OK = "ok"
        SKIP = "skip"
        CONFLICT = "conflict"
        NOT_FOUND = "not_found"

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

    def dry_run(self, pkg: Path, category: str) -> tuple[PlanResult, Path | None]:
        """
        Plan the PKG destination directory and check for conflicts.

        :param pkg: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: Tuple of (PlanResult, Planned directory Path or None)
        """
        if not pkg.exists():
            return self.PlanResult.NOT_FOUND, None

        target_folder = self.CATEGORY_MAP.get(category, "_unknown")
        pkg_dir = Path(os.environ["PKG_DIR"])
        target_dir = pkg_dir / target_folder
        target_path = target_dir / pkg.name

        if pkg.parent == target_dir:
            return self.PlanResult.SKIP, target_dir

        if target_path.exists():
            return self.PlanResult.CONFLICT, target_dir

        return self.PlanResult.OK, target_dir

    def run(self, pkg: Path, category: str) -> str | None:
        """
        Move the PKG file to its category folder.

        :param pkg: Path object representing the PKG file
        :param category: SFO category (e.g. "gd", "ac")
        :return: New path string if moved, otherwise None
        """
        plan_result, target_dir = self.dry_run(pkg, category)

        if plan_result == self.PlanResult.NOT_FOUND:
            log("error", "PKG file not found", message=f"{pkg}", module="AUTO_SORTER")
            return None

        if plan_result == self.PlanResult.SKIP:
            log("debug", "Skipping sort. PKG is already in the folder", message=f"{target_dir}", module="AUTO_SORTER")
            return None

        if plan_result == self.PlanResult.CONFLICT:
            log("error", "Failed to move PKG. Target already exists", message=f"{pkg.name}", module="AUTO_SORTER")
            error_dir = Path(os.environ["ERROR_DIR"])
            error_dir.mkdir(parents=True, exist_ok=True)
            conflict_path = error_dir / pkg.name
            counter = 1
            while conflict_path.exists():
                conflict_path = error_dir / f"{pkg.stem}_{counter}{pkg.suffix}"
                counter += 1
            pkg.rename(conflict_path)
            log("warn", "PKG moved to errors folder", message=f"{pkg.name} -> {conflict_path.name}", module="AUTO_SORTER")
            return None

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pkg.name
        pkg.rename(target_path)
        log("info", "PKG sorted successfully", message=f"{pkg.name} -> {target_dir.name}/{pkg.name}", module="AUTO_SORTER")
        return str(target_path)
