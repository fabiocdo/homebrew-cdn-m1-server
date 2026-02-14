import os
from pathlib import Path

from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.section import Section
from hb_store_m1.utils.file_utils import FileUtils
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.AUTO_ORGANIZER)


class AutoOrganizer:

    @staticmethod
    def dry_run(pkg: PKG) -> Output[Path | None]:

        # Step 1: Check PKG existence
        if not pkg.pkg_path.is_file():
            return Output(Status.NOT_FOUND, None)

        # Step 2: Check if the PKG filename is valid
        invalid_chars = set('<>:"/\\|?*')
        if pkg.pkg_path.name in {os.curdir, os.pardir} or any(
            ch in invalid_chars for ch in pkg.pkg_path.name
        ):
            return Output(Status.INVALID, None)

        # Step 3: Check PKG CONTENT_ID
        content_id = pkg.content_id

        if not content_id:
            return Output(Status.INVALID, None)

        # Step 4: Plan the new path and filename
        planned_name = f"{content_id}.pkg"
        app_type = pkg.app_type
        app_type_name = app_type.value if app_type else ""

        section_by_name = {section.name: section for section in Section.ALL}
        target_section = section_by_name.get(app_type_name, Section.UNKNOWN)
        target_path = target_section.path / planned_name

        if pkg.pkg_path.resolve() == target_path.resolve():
            return Output(Status.SKIP, target_path)

        if target_path.exists():
            return Output(Status.CONFLICT, target_path)

        return Output(Status.OK, target_path)

    @staticmethod
    def run(pkg: PKG) -> Path | None:
        dry_run_output = AutoOrganizer.dry_run(pkg)

        plan_result = dry_run_output.status
        target_path = dry_run_output.content

        if plan_result == Status.NOT_FOUND:
            log.log_error(f"PKG file [{pkg.pkg_path.name}] not found")
            return None

        if plan_result == Status.INVALID:
            log.log_error(
                f"Invalid or missing content_id in [{pkg.pkg_path.name}] SFO data"
            )
            return None

        if plan_result == Status.SKIP:
            log.log_debug(
                f"Skipping move/rename. PKG {pkg.pkg_path.name} is already in place"
            )
            return dry_run_output.content or pkg.pkg_path

        if plan_result == Status.CONFLICT:
            log.log_error(
                f"Failed to move/rename PKG [{pkg.pkg_path.name}]. Target {target_path.name} already exists"
            )
            return None

        if not target_path:
            log.log_error(f"Failed to resolve target path for {pkg.pkg_path.name}")
            return None

        if not FileUtils.move(pkg.pkg_path, target_path):
            return None

        log.log_info(
            f"PKG {pkg.pkg_path.name} moved/renamed successfully to {target_path}"
        )
        return target_path
