import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from hb_store_m1.models.fpkgi import FPKGI
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG, AppType
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.FPKGI_UTIL)


def _entry_md5(values_by_column: dict[str, object]) -> str:
    columns = [col.value for col in FPKGI.Column]
    payload = json.dumps(
        [values_by_column.get(name) for name in columns],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def _path_url(path: Path | None) -> str | None:
    if not path:
        return None
    return urljoin(Globals.ENVS.SERVER_URL, str(path))


def _pkg_size(pkg: PKG) -> int:
    if pkg.size:
        return int(pkg.size)
    if not pkg.pkg_path:
        return 0
    try:
        return int(pkg.pkg_path.stat().st_size)
    except OSError:
        return 0


def _read_json(path: Path) -> list[dict[str, object]] | None:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.log_error(f"Failed to read {path.name}: {exc}")
        return None
    if not isinstance(data, list):
        log.log_error(f"Invalid {path.name}. Expected a JSON list")
        return None
    return data


def _write_json(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _entry_from_pkg(pkg: PKG) -> dict[str, object]:
    return {
        FPKGI.Column.ID.value: pkg.content_id,
        FPKGI.Column.NAME.value: pkg.title,
        FPKGI.Column.VERSION.value: pkg.version,
        FPKGI.Column.PACKAGE.value: _path_url(pkg.pkg_path),
        FPKGI.Column.SIZE.value: _pkg_size(pkg),
        FPKGI.Column.DESC.value: None,
        FPKGI.Column.ICON.value: _path_url(pkg.icon0_png_path),
        FPKGI.Column.BG_IMAGE.value: _path_url(pkg.pic1_png_path),
    }


def _app_type_names() -> list[str]:
    return sorted({app_type.value for app_type in AppType})


class FPKGIUtils:
    @staticmethod
    def upsert(pkgs: list[PKG]) -> Output:
        if not pkgs:
            return Output(Status.SKIP, "Nothing to upsert")

        pkgs_by_type: dict[str, list[PKG]] = {}
        for pkg in pkgs:
            app_type = pkg.app_type.value if pkg.app_type else "unknown"
            pkgs_by_type.setdefault(app_type, []).append(pkg)

        log.log_info(f"Attempting to upsert {len(pkgs)} PKGs in FPKGI JSON...")

        updated_total = 0
        skipped_total = 0

        for app_type, pkgs_for_type in pkgs_by_type.items():
            json_path = Globals.PATHS.DATA_DIR_PATH / f"{app_type}.json"
            entries = _read_json(json_path)
            if entries is None:
                return Output(Status.ERROR, "Failed to read FPKGI JSON")

            index_by_id: dict[str, int] = {}
            hash_by_id: dict[str, str] = {}
            for idx, entry in enumerate(entries):
                entry_id = entry.get(FPKGI.Column.ID.value)
                if not entry_id:
                    continue
                index_by_id[entry_id] = idx
                hash_by_id[entry_id] = _entry_md5(entry)

            updated_for_type = 0
            for pkg in pkgs_for_type:
                entry = _entry_from_pkg(pkg)
                entry_id = entry.get(FPKGI.Column.ID.value)
                if not entry_id:
                    continue
                entry_hash = _entry_md5(entry)
                if hash_by_id.get(entry_id) == entry_hash:
                    skipped_total += 1
                    continue
                if entry_id in index_by_id:
                    entries[index_by_id[entry_id]] = entry
                else:
                    entries.append(entry)
                updated_for_type += 1

            if updated_for_type:
                _write_json(json_path, entries)
                updated_total += updated_for_type

        if skipped_total:
            log.log_info(f"Skipped {skipped_total} unchanged PKGs")
            return Output(Status.SKIP, None)

        log.log_info(f"{updated_total} PKGs upserted successfully")
        return Output(Status.OK, updated_total)

    @staticmethod
    def delete_by_content_ids(content_ids: list[str]) -> Output:
        if not content_ids:
            return Output(Status.SKIP, "Nothing to delete")

        deleted_total = 0
        target_ids = set(content_ids)

        for app_type in _app_type_names():
            json_path = Globals.PATHS.DATA_DIR_PATH / f"{app_type}.json"
            entries = _read_json(json_path)
            if entries is None:
                return Output(Status.ERROR, "Failed to read FPKGI JSON")
            if not entries:
                continue

            remaining = [
                entry
                for entry in entries
                if entry.get(FPKGI.Column.ID.value) not in target_ids
            ]
            removed = len(entries) - len(remaining)
            if removed:
                _write_json(json_path, remaining)
                deleted_total += removed

        log.log_info(f"{deleted_total} PKGs deleted successfully")
        return Output(Status.OK, deleted_total)


FPKGIUtils = FPKGIUtils()
