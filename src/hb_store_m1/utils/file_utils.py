from pathlib import Path

from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.FILE_UTIL)


class FileUtils:
    @staticmethod
    def _next_available_path(path: Path) -> Path:
        if not path.exists():
            return path

        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def optimize_png(path: Path) -> bool:
        if not path.exists():
            return False
        log.log_debug(
            f"PNG optimize skipped for {path.name}. No lossless compressor available.",
        )
        return False

    @staticmethod
    def move(
        path: Path,
        target_path: Path,
    ) -> Path | None:
        if not path.exists():
            log.log_warn(f"Skipping move. File not found: {path}")
            return None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.rename(target_path)
        except OSError as exc:
            log.log_error(f"Failed to move file: {exc}")
            return None
        return target_path

    @staticmethod
    def move_to_error(
        path: Path,
        errors_dir: Path,
        reason: str,
    ) -> Path | None:
        if not path.exists():
            log.log_warn(f"Skipping move to errors. File not found: {path}")
            return None

        errors_dir.mkdir(parents=True, exist_ok=True)
        target_path = FileUtils._next_available_path(errors_dir / path.name)

        moved_path = FileUtils.move(path, target_path)
        if not moved_path:
            return None

        log.log_warn(f"Moved to errors ({reason}): {target_path.name}")
        return target_path


FileUtils = FileUtils()
