import os
from pathlib import Path
from src.utils.pkg_utils import PkgUtils
from src.utils.index_cache import load_cache, save_cache, hash_file


def scan_pkgs(pkg_dir: Path, pkg_utils: PkgUtils) -> tuple[list[tuple[Path, dict | None]], bool]:
    """
    Scan for PKG files and extract SFO data.

    :param pkg_dir: Directory to scan for PKG files
    :param pkg_utils: PkgUtils instance
    :return: List of (pkg path, sfo data or None)
    """
    results: list[tuple[Path, dict | None]] = []
    files_cache, index_cache, meta = load_cache()
    new_cache: dict[str, dict] = {}
    any_changes = False
    base_url = os.environ["BASE_URL"].rstrip("/")
    if meta.get("base_url") != base_url:
        any_changes = True

    for pkg in pkg_dir.rglob("*.pkg"):
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

    save_cache(new_cache, index_cache, {"base_url": base_url})
    return results, any_changes
