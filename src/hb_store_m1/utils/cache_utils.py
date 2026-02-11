import json
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogColor
from hb_store_m1.models.output import Output, Status
from hb_store_m1.utils.log_utils import LogUtils


class CacheUtils:
    _SECTIONS = (
        str(Globals.PATHS.PKG_DIR_PATH.name),
        str(Globals.PATHS.APP_DIR_PATH.name),
        str(Globals.PATHS.DLC_DIR_PATH.name),
        str(Globals.PATHS.GAME_DIR_PATH.name),
        str(Globals.PATHS.SAVE_DIR_PATH.name),
        str(Globals.PATHS.UNKNOWN_DIR_PATH.name),
        str(Globals.PATHS.UPDATE_DIR_PATH.name),
        str(Globals.PATHS.MEDIA_DIR_PATH.name),
    )

    @staticmethod
    def read_pkg_cache() -> (
        Output[dict[str, dict[str, dict[str, str] | dict[str, int]]]]
    ):
        store_cache_json_file_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH

        if not store_cache_json_file_path.exists():
            LogUtils.log_debug(
                f"Skipping {store_cache_json_file_path.name.upper()} read. File not found"
            )
            return Output(Status.NOT_FOUND, {})

        try:
            data = json.loads(store_cache_json_file_path.read_text("utf-8"))

        except (json.JSONDecodeError, OSError) as e:

            LogUtils.log_error(f"Failed to read {store_cache_json_file_path.name}: {e}")
            return Output(Status.ERROR, {})

        return Output(Status.OK, data)

    @staticmethod
    def write_pkg_cache(
        path: Path | None = None,
    ) -> Output[dict[str, dict[str, dict[str, str] | dict[str, int]]]]:
        store_cache_path = path or Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        pkg_dir_path = Globals.PATHS.PKG_DIR_PATH

        if not pkg_dir_path.exists():
            LogUtils.log_debug(
                f"Skipping {pkg_dir_path.name.upper()} scan. Directory not found"
            )
            return Output(Status.NOT_FOUND, {})

        cache: dict[str, dict[str, dict[str, str] | dict[str, int]]] = {
            section: {
                "meta": {"count": 0, "total_size": 0, "latest_mtime": 0},
                "content": {},
            }
            for section in CacheUtils._SECTIONS
        }

        def add_pkg(section: str, pkg_path: Path) -> None:
            if not pkg_path.is_file():
                return
            suffix = pkg_path.suffix.lower()
            if section == "_media":
                if suffix != ".png":
                    return
            elif suffix != ".pkg":
                return
            try:
                stat = pkg_path.stat()
            except OSError as exc:
                LogUtils.log_warn(f"Failed to stat {pkg_path.name}: {exc}")
                return
            meta = cache[section]["meta"]
            if isinstance(meta, dict):
                meta["count"] = int(meta.get("count", 0)) + 1
                meta["total_size"] = int(meta.get("total_size", 0)) + int(stat.st_size)
                meta["latest_mtime"] = max(
                    int(meta.get("latest_mtime", 0)), int(stat.st_mtime_ns)
                )
            cache[section]["content"][
                pkg_path.name
            ] = f"{stat.st_size}|{stat.st_mtime_ns}"

        for pkg_path in pkg_dir_path.iterdir():
            add_pkg("pkg", pkg_path)

        for section in CacheUtils._SECTIONS:
            if section == "pkg":
                continue
            section_path = pkg_dir_path / section
            if not section_path.exists():
                continue
            for pkg_path in section_path.iterdir():
                add_pkg(section, pkg_path)

        totals = []
        for section in CacheUtils._SECTIONS:
            meta = cache[section]["meta"]
            count = meta.get("count", 0) if isinstance(meta, dict) else 0
            totals.append(f"{section}={count}")
        LogUtils.log_info("Cache scan totals: " + " | ".join(totals))

        store_cache_path.parent.mkdir(parents=True, exist_ok=True)
        store_cache_path.write_text(
            json.dumps(cache, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return Output(Status.OK, cache)

    @staticmethod
    def compare_pkg_cache() -> Output[dict[str, dict[str, list[str]] | list[str]]]:
        store_cache_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        temp_path = store_cache_path.with_suffix(".tmp")

        current_output = CacheUtils.write_pkg_cache(temp_path)
        cached_output = CacheUtils.read_pkg_cache()

        current = current_output.content or {}
        cached = cached_output.content or {}

        added: dict[str, list[str]] = {}
        removed: dict[str, list[str]] = {}
        updated: dict[str, list[str]] = {}
        changed_sections: list[str] = []
        summary_lines: list[str] = []

        for section in CacheUtils._SECTIONS:
            current_section = current.get(section, {})
            cached_section = cached.get(section, {})
            current_meta = current_section.get("meta", {})
            cached_meta = cached_section.get("meta", {})
            current_content = current_section.get("content", {})
            cached_content = cached_section.get("content", {})
            if not isinstance(current_content, dict):
                current_content = {}
            if not isinstance(cached_content, dict):
                cached_content = {}
            current_keys = set(current_content)
            cached_keys = set(cached_content)

            added[section] = sorted(current_keys - cached_keys)
            removed[section] = sorted(cached_keys - current_keys)
            updated[section] = sorted(
                key
                for key in current_keys & cached_keys
                if current_content[key] != cached_content[key]
            )
            added_count = len(added[section])
            updated_count = len(updated[section])
            removed_count = len(removed[section])
            if (
                current_meta != cached_meta
                or added[section]
                or removed[section]
                or updated[section]
            ):
                changed_sections.append(section)
                summary = (
                    f"{section.upper()} "
                    f"{LogColor.GREEN if added_count != 0 else LogColor.RESET}+{added_count}{LogColor.RESET} "
                    f"{LogColor.YELLOW if updated_count != 0 else LogColor.RESET}"
                    f"~{updated_count}{LogColor.RESET} "
                    f"{LogColor.RED if removed_count != 0 else LogColor.RESET}-{removed_count}{LogColor.RESET}"
                )
                summary_lines.append(summary)

        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError as exc:
            LogUtils.log_warn(f"Failed to remove temp cache file: {exc}")

        if summary_lines:
            LogUtils.log_info("Cache changes summary: " + " | ".join(summary_lines))

        return Output(
            Status.OK,
            {
                "added": added,
                "updated": updated,
                "removed": removed,
                "changed": sorted(changed_sections),
            },
        )


CacheUtils = CacheUtils()
