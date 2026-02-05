import os
import concurrent.futures
from pathlib import Path
from src.utils.pkg_utils import PkgUtils
from src.utils.log_utils import log
from src.utils.index_cache import load_cache, save_cache, DB_SCHEMA_VERSION
from src.utils.url_utils import build_base_url


def scan_pkgs(
        pkg_dir: Path,
        pkg_utils: PkgUtils,
        pkgs: list[Path] | None = None,
        batch_size: int | None = None,
        workers: int | None = None,
        log_module: str | None = None,
) -> tuple[list[tuple[Path, dict | None]], bool]:
    results: list[tuple[Path, dict | None]] = []
    files_cache, index_cache, meta = load_cache()
    new_cache: dict[str, dict] = {}
    inode_cache: dict[int, dict] = {}
    for entry in files_cache.values():
        inode = entry.get("inode")
        if isinstance(inode, int):
            inode_cache[inode] = entry
    any_changes = False
    base_url = build_base_url().rstrip("/")
    if meta.get("base_url") != base_url:
        any_changes = True
    if meta.get("db_schema_version") != DB_SCHEMA_VERSION:
        any_changes = True

    pkg_list = pkgs if pkgs is not None else list(pkg_dir.rglob("*.pkg"))
    if batch_size and batch_size > 0:
        batches = [
            pkg_list[i: i + batch_size]
            for i in range(0, len(pkg_list), batch_size)
        ]
    else:
        batches = [pkg_list]

    total_batches = max(1, len(batches))

    def _scan_one(pkg: Path) -> tuple[Path, dict | None, dict | None, bool]:
        try:
            stat = pkg.stat()
        except FileNotFoundError:
            return pkg, None, None, True
        key = str(pkg)
        entry = files_cache.get(key)
        inode_entry = inode_cache.get(stat.st_ino) if entry is None else None

        sfo_data = None
        file_hash = None
        changed = not entry or entry.get("size") != stat.st_size or entry.get("mtime") != stat.st_mtime
        if not changed:
            sfo_data = entry.get("sfo")
            file_hash = entry.get("hash")
        elif inode_entry and inode_entry.get("size") == stat.st_size and inode_entry.get("mtime") == stat.st_mtime:
            sfo_data = inode_entry.get("sfo")
            file_hash = inode_entry.get("hash")
        else:
            file_hash = entry.get("hash") if entry else None
            sfo_result, sfo_payload = pkg_utils.extract_pkg_data(pkg)
            if sfo_result == PkgUtils.ExtractResult.OK:
                sfo_data = sfo_payload

        cache_entry = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "inode": stat.st_ino,
            "hash": file_hash,
            "sfo": sfo_data,
        }
        return pkg, sfo_data, cache_entry, changed

    for batch_index, batch in enumerate(batches, start=1):
        if log_module and batch:
            log(
                "info",
                f"Scanning batch {batch_index}/{total_batches} ({len(batch)} PKG(s))...",
                module=log_module,
            )
        progress_every = max(1, len(batch) // 5) if batch else 1
        processed = 0
        batch_workers = workers or 1
        if batch_workers < 1:
            batch_workers = 1
        if batch_workers > 1 and len(batch) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as pool:
                futures = [pool.submit(_scan_one, pkg) for pkg in batch]
                for future in concurrent.futures.as_completed(futures):
                    pkg, sfo_data, cache_entry, changed = future.result()
                    processed += 1
                    if log_module and (processed % progress_every == 0 or processed == len(batch)):
                        log(
                            "debug",
                            f"Batch {batch_index}/{total_batches} progress: {processed}/{len(batch)}",
                            module=log_module,
                        )
                    if cache_entry is None:
                        any_changes = True
                        continue
                    if changed:
                        any_changes = True
                    new_cache[str(pkg)] = cache_entry
                    results.append((pkg, sfo_data))
        else:
            for pkg in batch:
                pkg, sfo_data, cache_entry, changed = _scan_one(pkg)
                processed += 1
                if log_module and (processed % progress_every == 0 or processed == len(batch)):
                    log(
                        "debug",
                        f"Batch {batch_index}/{total_batches} progress: {processed}/{len(batch)}",
                        module=log_module,
                    )
                if cache_entry is None:
                    any_changes = True
                    continue
                if changed:
                    any_changes = True
                new_cache[str(pkg)] = cache_entry
                results.append((pkg, sfo_data))

    removed = set(files_cache.keys()) - set(new_cache.keys())
    if removed:
        any_changes = True

    meta_out = dict(meta)
    meta_out["base_url"] = base_url
    save_cache(new_cache, index_cache, meta_out)
    return results, any_changes
