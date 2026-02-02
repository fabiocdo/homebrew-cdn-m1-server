from __future__ import annotations

import os
from pathlib import Path
from src.utils.pkg_utils import PkgUtils
from src.utils.log_utils import log
from src.utils.index_cache import load_cache, save_cache, hash_file, DB_SCHEMA_VERSION


def scan_pkgs(
    pkg_dir: Path,
    pkg_utils: PkgUtils,
    pkgs: list[Path] | None = None,
    batch_size: int | None = None,
    log_module: str | None = None,
) -> tuple[list[tuple[Path, dict | None]], bool]:
    """
    Scan for PKGs, extract SFO data, and detect changes.

    :param pkg_dir: Directory to scan for PKG files
    :param pkg_utils: PkgUtils instance
    :param pkgs: Optional list of PKG paths to scan
    :param batch_size: Optional batch size for scanning
    :param log_module: Optional module tag for progress logs
    :return: (list of (pkg path, sfo data or None), has_changes flag)
    """
    results: list[tuple[Path, dict | None]] = []
    files_cache, index_cache, meta = load_cache()
    new_cache: dict[str, dict] = {}
    any_changes = False
    base_url = os.environ["BASE_URL"].rstrip("/")
    if meta.get("base_url") != base_url:
        any_changes = True
    if meta.get("db_schema_version") != DB_SCHEMA_VERSION:
        any_changes = True

    pkg_list = pkgs if pkgs is not None else list(pkg_dir.rglob("*.pkg"))
    if batch_size and batch_size > 0:
        batches = [
            pkg_list[i : i + batch_size]
            for i in range(0, len(pkg_list), batch_size)
        ]
    else:
        batches = [pkg_list]

    total_batches = max(1, len(batches))
    for batch_index, batch in enumerate(batches, start=1):
        if log_module and batch:
            log(
                "info",
                f"Scanning batch {batch_index}/{total_batches} ({len(batch)} PKG(s))...",
                module=log_module,
            )
        for pkg in batch:
            stat = pkg.stat()
            key = str(pkg)
            entry = files_cache.get(key)

            sfo_data = None
            file_hash = None
            changed = not entry or entry.get("size") != stat.st_size or entry.get("mtime") != stat.st_mtime
            if changed:
                any_changes = True

            if not changed:
                sfo_data = entry.get("sfo")
                file_hash = entry.get("hash")
            else:
                file_hash = hash_file(pkg)
                cached_hash = entry.get("hash") if entry else None
                if cached_hash and file_hash == cached_hash:
                    sfo_data = entry.get("sfo")
                else:
                    sfo_result, sfo_payload = pkg_utils.extract_pkg_data(pkg)
                    if sfo_result == PkgUtils.ExtractResult.OK:
                        sfo_data = sfo_payload

            new_cache[key] = {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "hash": file_hash,
                "sfo": sfo_data,
            }
            results.append((pkg, sfo_data))

    removed = set(files_cache.keys()) - set(new_cache.keys())
    if removed:
        any_changes = True

    meta_out = dict(meta)
    meta_out["base_url"] = base_url
    save_cache(new_cache, index_cache, meta_out)
    return results, any_changes
