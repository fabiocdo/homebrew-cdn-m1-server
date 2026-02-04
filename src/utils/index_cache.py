

import json
import os
import hashlib
from pathlib import Path

CACHE_VERSION = 2
DB_SCHEMA_VERSION = 6
CACHE_FILENAME = "index-cache.json"


def _cache_path() -> Path:
    





    return Path(os.environ["CACHE_DIR"]) / CACHE_FILENAME


def load_cache() -> tuple[dict[str, dict], dict[str, dict], dict[str, str]]:
    





    path = _cache_path()
    if not path.exists():
        return {}, {}, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, {}, {}
    if not isinstance(data, dict):
        return {}, {}, {}
    if data.get("version") != CACHE_VERSION:
        return {}, {}, {}
    files = data.get("files", {})
    index = data.get("index", {})
    meta = data.get("meta", {})
    if not isinstance(files, dict):
        files = {}
    if not isinstance(index, dict):
        index = {}
    if not isinstance(meta, dict):
        meta = {}
    return files, index, meta


def save_cache(files: dict[str, dict], index: dict[str, dict], meta: dict[str, str]) -> None:
    







    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": CACHE_VERSION, "files": files, "index": index, "meta": meta}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    






    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
