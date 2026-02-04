

import os
from pathlib import Path
from src.utils import log
from src.models.sorter_models import SorterPlanResult


class AutoSorter:
    








    PlanResult = SorterPlanResult

    def dry_run(self, pkg: Path, app_type: str) -> tuple[PlanResult, Path | None]:
        






        if not pkg.exists():
            return self.PlanResult.NOT_FOUND, None

        target_folder = app_type
        pkg_dir = Path(os.environ["PKG_DIR"])
        target_dir = pkg_dir / target_folder
        target_path = target_dir / pkg.name

        if pkg.parent == target_dir:
            return self.PlanResult.SKIP, target_dir

        if target_path.exists():
            return self.PlanResult.CONFLICT, target_dir

        return self.PlanResult.OK, target_dir

    def run(self, pkg: Path, app_type: str) -> str | None:
        






        plan_result, target_dir = self.dry_run(pkg, app_type)

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
        log("info", "PKG sorted successfully", message=f"{pkg.name} -> {target_path}", module="AUTO_SORTER")
        return str(target_path)
