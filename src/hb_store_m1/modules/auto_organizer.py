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
    _INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
    _SECTIONS = {section.name: section for section in Section.ALL}

    @classmethod
    def _target_path_for_pkg(cls, pkg: PKG) -> Path | None:
        if not pkg.content_id:
            return None
        app_type = pkg.app_type.value if pkg.app_type else ""
        section = cls._SECTIONS.get(app_type, Section.UNKNOWN)
        return section.path / f"{pkg.content_id}.pkg"

    @classmethod
    def _has_invalid_filename(cls, file_name: str) -> bool:
        if file_name in {os.curdir, os.pardir}:
            return True
        return any(ch in cls._INVALID_FILENAME_CHARS for ch in file_name)

    @classmethod
    def dry_run(cls, pkg: PKG) -> Output[Path | None]:
        if not pkg.pkg_path.is_file():
            return Output(Status.NOT_FOUND, None)

        if cls._has_invalid_filename(pkg.pkg_path.name):
            return Output(Status.INVALID, None)

        target_path = cls._target_path_for_pkg(pkg)
        if not target_path:
            return Output(Status.INVALID, None)

        if pkg.pkg_path.resolve() == target_path.resolve():
            return Output(Status.SKIP, target_path)

        if target_path.exists():
            return Output(Status.CONFLICT, target_path)

        return Output(Status.OK, target_path)

    @classmethod
    def run(cls, pkg: PKG) -> Path | None:
        dry_run_output = cls.dry_run(pkg)

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
