import json
from pathlib import Path

from hb_store_m1.models.cache import CacheSection, CACHE_ADAPTER
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogColor, LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.section import Section, SectionEntry
from hb_store_m1.utils.log_utils import LogUtils
from pydantic import ValidationError


class CacheUtils:
    _SECTIONS = Section.ALL

    @staticmethod
    def read_pkg_cache():
        store_cache_json_file_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH

        if not store_cache_json_file_path.exists():
            LogUtils.log_debug(
                f"Skipping {store_cache_json_file_path.name.upper()} read. File not found",
                LogModule.CACHE_UTIL,
            )
            return Output(Status.NOT_FOUND, {})

        try:
            data = CACHE_ADAPTER.validate_json(
                store_cache_json_file_path.read_text("utf-8")
            )
        except (OSError, ValueError, ValidationError) as e:
            LogUtils.log_error(
                f"Failed to read {store_cache_json_file_path.name}: {e}",
                LogModule.CACHE_UTIL,
            )
            return Output(Status.ERROR, {})

        return Output(Status.OK, data)

    @staticmethod
    def write_pkg_cache(path: Path | None = None):
        store_cache_path = path or Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        pkg_dir_path = Globals.PATHS.PKG_DIR_PATH

        if not pkg_dir_path.exists():
            LogUtils.log_debug(
                f"Skipping {pkg_dir_path.name.upper()} scan. Directory not found",
                LogModule.CACHE_UTIL,
            )
            return Output(Status.NOT_FOUND, {})

        cache = {section.name: CacheSection() for section in CacheUtils._SECTIONS}

        for section in CacheUtils._SECTIONS:
            section_path = section.path

            if not section_path.exists():
                continue

            for pkg_path in section_path.iterdir():
                if not section.accepts(pkg_path):
                    continue

                try:
                    stat = pkg_path.stat()

                except OSError as exc:
                    LogUtils.log_warn(
                        f"Failed to stat {pkg_path.name}: {exc}",
                        LogModule.CACHE_UTIL,
                    )
                    continue

                section_cache = cache[section.name]
                section_cache.meta.count += 1
                section_cache.meta.total_size += int(stat.st_size)
                section_cache.meta.latest_mtime = max(
                    section_cache.meta.latest_mtime, int(stat.st_mtime_ns)
                )
                section_cache.content[pkg_path.name] = (
                    f"{stat.st_size}|{stat.st_mtime_ns}"
                )

        store_cache_path.parent.mkdir(parents=True, exist_ok=True)
        store_cache_path.write_text(
            json.dumps(
                CACHE_ADAPTER.dump_python(cache),
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return Output(Status.OK, cache)

    @staticmethod
    def compare_pkg_cache():
        store_cache_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        temp_path = store_cache_path.with_suffix(".tmp")

        current_output = CacheUtils.write_pkg_cache(temp_path)
        cached_output = CacheUtils.read_pkg_cache()

        current = current_output.content or {}
        cached = cached_output.content or {}

        added = {}
        removed = {}
        updated = {}
        changed_sections = []
        summary_lines = []

        for section in CacheUtils._SECTIONS:
            section_name = section.name
            current_section = current.get(section_name, CacheSection())
            cached_section = cached.get(section_name, CacheSection())
            current_meta = current_section.meta
            cached_meta = cached_section.meta
            current_content = current_section.content
            cached_content = cached_section.content
            current_keys = set(current_content)
            cached_keys = set(cached_content)

            added[section_name] = sorted(current_keys - cached_keys)
            removed[section_name] = sorted(cached_keys - current_keys)
            updated[section_name] = sorted(
                key
                for key in current_keys & cached_keys
                if current_content[key] != cached_content[key]
            )
            added_count = len(added[section_name])
            updated_count = len(updated[section_name])
            removed_count = len(removed[section_name])
            if (
                current_meta.model_dump() != cached_meta.model_dump()
                or added[section_name]
                or removed[section_name]
                or updated[section_name]
            ):
                changed_sections.append(section_name)
                summary = (
                    f"{section_name.upper()}: "
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
            LogUtils.log_warn(
                f"Failed to remove temp cache file: {exc}", LogModule.CACHE_UTIL
            )

        if summary_lines:
            LogUtils.log_info(
                "Cache changes summary: " + ", ".join(summary_lines),
                LogModule.CACHE_UTIL,
            )

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
