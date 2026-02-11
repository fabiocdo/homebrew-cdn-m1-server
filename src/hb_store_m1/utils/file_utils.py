from pathlib import Path

from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.log_utils import LogUtils


class FileUtils:
    @staticmethod
    def optimize_png(
        path: Path,
        module: LogModule | None = None,
    ) -> bool:
        if not path.exists():
            return False
        LogUtils.log_debug(
            f"PNG optimize skipped for {path.name}. No lossless compressor available.",
            module,
        )
        return False

    @staticmethod
    def move(
        path: Path,
        target_path: Path,
        module: LogModule | None = None,
    ) -> Path | None:
        if not path.exists():
            LogUtils.log_warn(f"Skipping move. File not found: {path}", module)
            return None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.rename(target_path)
        except OSError as exc:
            LogUtils.log_error(f"Failed to move file: {exc}", module)
            return None
        return target_path

    @staticmethod
    def move_to_error(
        path: Path,
        errors_dir: Path,
        reason: str,
        module: LogModule | None = None,
    ) -> Path | None:
        if not path.exists():
            LogUtils.log_warn(
                f"Skipping move to errors. File not found: {path}", module
            )
            return None

        errors_dir.mkdir(parents=True, exist_ok=True)
        target_path = errors_dir / path.name
        if target_path.exists():
            counter = 1
            while True:
                candidate = errors_dir / f"{path.stem}_{counter}{path.suffix}"
                if not candidate.exists():
                    target_path = candidate
                    break
                counter += 1

        moved_path = FileUtils.move(path, target_path, module)
        if not moved_path:
            return None

        LogUtils.log_warn(f"Moved to errors ({reason}): {target_path.name}", module)
        return target_path


FileUtils = FileUtils()
