from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import final

from homebrew_cdn_m1_server.domain.models.app_config import RuntimePaths


@final
class FilesystemRepository:
    def __init__(self, paths: RuntimePaths) -> None:
        self._paths = paths

    def ensure_layout(self) -> None:
        dirs = [
            self._paths.data_dir,
            self._paths.internal_dir,
            self._paths.share_dir,
            self._paths.hb_store_share_dir,
            self._paths.fpkgi_share_dir,
            self._paths.catalog_dir,
            self._paths.cache_dir,
            self._paths.logs_dir,
            self._paths.errors_dir,
            self._paths.hb_store_update_dir,
            self._paths.pkg_root,
            self._paths.media_dir,
            self._paths.app_dir,
            self._paths.game_dir,
            self._paths.dlc_dir,
            self._paths.pkg_update_dir,
            self._paths.save_dir,
            self._paths.unknown_dir,
        ]
        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def ensure_public_index(self, source_path: Path) -> None:
        if self._paths.public_index_path.exists():
            return
        if not source_path.exists():
            return

        self._paths.public_index_path.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copyfile(source_path, self._paths.public_index_path)

    def scan_pkg_files(self) -> list[Path]:
        if not self._paths.pkg_root.exists():
            return []

        files: list[Path] = []
        for pkg in self._paths.pkg_root.rglob("*.pkg"):
            if not pkg.is_file():
                continue
            if self._paths.media_dir in pkg.parents:
                continue
            files.append(pkg)
        return sorted(files)

    def stat(self, pkg_path: Path) -> tuple[int, int]:
        stat = pkg_path.stat()
        return int(stat.st_size), int(stat.st_mtime_ns)

    def move_to_canonical(self, pkg_path: Path, app_type: str, content_id: str) -> Path:
        target_dir = self._paths.pkg_root / app_type
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{content_id}.pkg"

        if pkg_path.resolve() == target.resolve():
            return target

        if target.exists():
            raise FileExistsError(f"Target already exists: {target}")

        moved = Path(shutil.move(str(pkg_path), str(target)))
        return moved

    def move_to_errors(self, pkg_path: Path, reason: str) -> Path:
        self._paths.errors_dir.mkdir(parents=True, exist_ok=True)
        stamp = str(int(time.time()))
        safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reason)
        destination = self._paths.errors_dir / (
            f"{pkg_path.stem}.{safe_reason}.{stamp}{pkg_path.suffix}"
        )
        return Path(shutil.move(str(pkg_path), str(destination)))
