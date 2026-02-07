from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.utils.log import LogUtils


class AutoFormatter:
    @staticmethod
    def dry_run(pkg: Path, sfo_data: dict) -> Output:

        if not pkg.exists():
            return Output(Status.NOT_FOUND, pkg.name)

        content_id = str((sfo_data or {}).get("content_id", "").strip())
        if not content_id:
            return Output(Status.INVALID, pkg.name)

        invalid_chars = '<>:"/\\|?*'
        if content_id in {".", ".."} or any(ch in content_id for ch in invalid_chars):
            return Output(Status.INVALID, pkg.name)

        planned_name = content_id
        if not planned_name.lower().endswith(".pkg"):
            planned_name = f"{planned_name}.pkg"

        if pkg.name == planned_name:
            return Output(Status.SKIP, pkg.name)

        target_path = pkg.with_name(planned_name)
        if target_path.exists():
            return Output(Status.CONFLICT, pkg.name)

        return Output(Status.OK, pkg.name)

    @staticmethod
    def run(pkg: Path, sfo_data: dict) -> str | None:
        errors_dir = Globals.PATHS.ERRORS_DIR_PATH
        plan_result, planned_name = AutoFormatter.dry_run(pkg, sfo_data)

        if plan_result == Status.NOT_FOUND:
            LogUtils.log_error(f"PKG file [{pkg}] not found", LogModule.AUTO_FORMATTER)
            return None

        if plan_result == Status.INVALID:
            LogUtils.log_error(
                f"Invalid or missing content_id in [{pkg.name}] SFO data",
                LogModule.AUTO_FORMATTER,
            )
            return None

        if plan_result == Status.SKIP:
            LogUtils.log_debug(
                f"Skipping rename. PKG [{planned_name}] is already renamed",
                LogModule.AUTO_FORMATTER,
            )
            return None

        if plan_result == Status.CONFLICT:
            LogUtils.log_error(
                f"Failed to rename PKG [{pkg.name}]. Target name [{planned_name}] already exists",
                LogModule.AUTO_FORMATTER,
            )

            conflict_path = errors_dir / pkg.name
            counter = 1

            while conflict_path.exists():
                conflict_path = errors_dir / f"{pkg.stem}_{counter}{pkg.suffix}"
                counter += 1

            pkg.rename(conflict_path)
            LogUtils.log_warn(
                f"PKG {pkg.name} moved to errors folder: {conflict_path.name}",
                LogModule.AUTO_FORMATTER,
            )
            return None

        target_path = pkg.with_name(planned_name)
        pkg.rename(target_path)

        LogUtils.log_info(
            f"PKG {pkg.name} renamed successfully to {planned_name}",
            LogModule.AUTO_FORMATTER,
        )
        return planned_name
