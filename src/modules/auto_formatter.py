import os
from pathlib import Path
from src.utils import log
from src.models.formatter_models import FormatterPlanResult


class AutoFormatter:
    PlanResult = FormatterPlanResult

    def dry_run(self, pkg: Path, sfo_data: dict) -> tuple[PlanResult, str | None]:

        if not pkg.exists():
            return self.PlanResult.NOT_FOUND, pkg.name

        content_id = str((sfo_data or {}).get("content_id", "")).strip()
        if not content_id:
            return self.PlanResult.INVALID, pkg.name

        invalid_chars = '<>:"/\\|?*'
        if content_id in {".", ".."} or any(ch in content_id for ch in invalid_chars):
            return self.PlanResult.INVALID, pkg.name

        planned_name = content_id
        if not planned_name.lower().endswith(".pkg"):
            planned_name = f"{planned_name}.pkg"

        if pkg.name == planned_name:
            return self.PlanResult.SKIP, planned_name

        target_path = pkg.with_name(planned_name)
        if target_path.exists():
            return self.PlanResult.CONFLICT, planned_name

        return self.PlanResult.OK, planned_name

    def run(self, pkg: Path, sfo_data: dict) -> str | None:

        plan_result, planned_name = self.dry_run(pkg, sfo_data)

        if plan_result == self.PlanResult.NOT_FOUND:
            log("error", "PKG file not found", message=f"{pkg}", module="AUTO_FORMATTER")
            return None

        if plan_result == self.PlanResult.INVALID:
            log(
                "error",
                "Invalid or missing content_id in SFO data",
                message=f"{pkg.name}",
                module="AUTO_FORMATTER",
            )
            return None

        if plan_result == self.PlanResult.SKIP:
            log("debug", "Skipping rename. PKG is already renamed", message=f"{planned_name}", module="AUTO_FORMATTER")
            return None

        if plan_result == self.PlanResult.CONFLICT:
            log("error", "Failed to rename PKG. Target name already exists", message=f"{pkg.name} -> {planned_name}",
                module="AUTO_FORMATTER")
            error_dir = Path(os.environ["ERROR_DIR"])
            error_dir.mkdir(parents=True, exist_ok=True)
            conflict_path = error_dir / pkg.name
            counter = 1
            while conflict_path.exists():
                conflict_path = error_dir / f"{pkg.stem}_{counter}{pkg.suffix}"
                counter += 1
            pkg.rename(conflict_path)
            log("warn", "PKG moved to errors folder", message=f"{pkg.name} -> {conflict_path.name}",
                module="AUTO_FORMATTER")
            return None

        target_path = pkg.with_name(planned_name)
        pkg.rename(target_path)
        log("info", "PKG renamed successfully", message=f"{pkg.name} -> {planned_name}", module="AUTO_FORMATTER")
        return planned_name
