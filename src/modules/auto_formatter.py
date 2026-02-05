from pathlib import Path

from src.models import Output, LoggingModule, Global, PKG
from src.utils import log_error, log_debug, log_warn, log_info

class AutoFormatter:
    @staticmethod
    def dry_run(pkg: Path, sfo_data: dict) -> tuple[Output, str | None]:

        if not pkg.exists():
            return Output.NOT_FOUND, pkg.name

        content_id = str((sfo_data or {}).get("content_id", "").strip())
        if not content_id:
            return Output.INVALID, pkg.name

        invalid_chars = '<>:"/\\|?*'
        if content_id in {".", ".."} or any(ch in content_id for ch in invalid_chars):
            return Output.INVALID, pkg.name

        planned_name = content_id
        if not planned_name.lower().endswith(".pkg"):
            planned_name = f"{planned_name}.pkg"

        if pkg.name == planned_name:
            return Output.SKIP, planned_name

        target_path = pkg.with_name(planned_name)
        if target_path.exists():
            return Output.CONFLICT, planned_name

        return Output.OK, planned_name

    @staticmethod
    def run(pkg: Path, sfo_data: dict) -> str | None:
        errors_dir = Global.PATHS.ERRORS_DIR_PATH
        plan_result, planned_name = AutoFormatter.dry_run(pkg, sfo_data)

        if plan_result == Output.NOT_FOUND:
            log_error(f"PKG file [{pkg}] not found", LoggingModule.AUTO_FORMATTER)
            return None

        if plan_result == Output.INVALID:
            log_error(f"Invalid or missing content_id in [{pkg.name}] SFO data", LoggingModule.AUTO_FORMATTER)
            return None

        if plan_result == Output.SKIP:
            log_debug(f"Skipping rename. PKG [{planned_name}] is already renamed", LoggingModule.AUTO_FORMATTER)
            return None

        if plan_result == Output.CONFLICT:
            log_error(
                f"Failed to rename PKG [{pkg.name}]. Target name [{planned_name}] already exists",
                LoggingModule.AUTO_FORMATTER,
            )

            conflict_path = errors_dir / pkg.name
            counter = 1

            while conflict_path.exists():
                conflict_path = errors_dir / f"{pkg.stem}_{counter}{pkg.suffix}"
                counter += 1

            pkg.rename(conflict_path)
            log_warn(
                f"PKG {pkg.name} moved to errors folder: {conflict_path.name}",
                LoggingModule.AUTO_FORMATTER,
            )
            return None

        target_path = pkg.with_name(planned_name)
        pkg.rename(target_path)

        log_info(f"PKG {pkg.name} renamed successfully to {planned_name}", LoggingModule.AUTO_FORMATTER)
        return planned_name
