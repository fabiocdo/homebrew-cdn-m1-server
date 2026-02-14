import json
import re
from pathlib import Path

from hb_store_m1.models.cache import CacheSection, CACHE_ADAPTER
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogColor, LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.section import Section
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.CACHE_UTIL)
from pydantic import ValidationError


class CacheUtils:
    _SECTIONS = Section.ALL
    _MEDIA_SECTION = "_media"
    _MEDIA_SUFFIXES = ("_icon0", "_pic0", "_pic1")
    _CONTENT_ID_PATTERN = re.compile(
        r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$"
    )

    @staticmethod
    def _parse_cache_entry(content_id: str, value: str) -> tuple[str, str, str] | None:
        parts = value.split("|", 2)
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        if len(parts) >= 2:
            return parts[0], parts[1], f"{content_id}.pkg"
        return None

    @staticmethod
    def _filename_from_cache_entry(content_id: str, value: str) -> str:
        parsed = CacheUtils._parse_cache_entry(content_id, value)
        if parsed:
            return parsed[2]
        return f"{content_id}.pkg"

    @staticmethod
    def _cached_index_by_section(
        cached: dict[str, CacheSection],
    ) -> dict[str, dict[str, tuple[str, str, str]]]:
        cached_index_by_section: dict[str, dict[str, tuple[str, str, str]]] = {}
        for section in CacheUtils._SECTIONS:
            if section.name == CacheUtils._MEDIA_SECTION:
                continue
            cached_section = cached.get(section.name)
            if not cached_section:
                continue

            index: dict[str, tuple[str, str, str]] = {}
            for content_id, value in cached_section.content.items():
                parsed = CacheUtils._parse_cache_entry(content_id, value)
                if not parsed:
                    continue
                size_str, mtime_str, filename = parsed
                index[filename] = (content_id, size_str, mtime_str)
            cached_index_by_section[section.name] = index
        return cached_index_by_section

    @staticmethod
    def _content_id_from_media_key(media_key: str) -> str | None:
        for suffix in CacheUtils._MEDIA_SUFFIXES:
            if media_key.endswith(suffix):
                return media_key[: -len(suffix)]
        return None

    @staticmethod
    def _cache_value(size: int, mtime_ns: int, filename: str) -> str:
        return f"{size}|{mtime_ns}|{filename}"

    @staticmethod
    def _is_content_id(value: str) -> bool:
        return bool(CacheUtils._CONTENT_ID_PATTERN.match(value or ""))

    @staticmethod
    def _current_file_map(current_content: dict[str, str]) -> dict[str, str]:
        return {
            key: CacheUtils._filename_from_cache_entry(key, value)
            for key, value in current_content.items()
        }

    @staticmethod
    def _section_changes(
        current_section: CacheSection, cached_section: CacheSection
    ) -> tuple[list[str], list[str], list[str]]:
        current_keys = set(current_section.content)
        cached_keys = set(cached_section.content)
        added = sorted(current_keys - cached_keys)
        removed = sorted(cached_keys - current_keys)
        updated = sorted(
            key
            for key in current_keys & cached_keys
            if current_section.content[key] != cached_section.content[key]
        )
        return added, removed, updated

    @staticmethod
    def _section_summary(
        section_name: str, added: int, updated: int, removed: int
    ) -> str:
        return (
            f"{section_name.upper()}: "
            f"{LogColor.BRIGHT_GREEN if added != 0 else LogColor.RESET}+{added}{LogColor.RESET} "
            f"{LogColor.BRIGHT_YELLOW if updated != 0 else LogColor.RESET}"
            f"~{updated}{LogColor.RESET} "
            f"{LogColor.BRIGHT_RED if removed != 0 else LogColor.RESET}-{removed}{LogColor.RESET}"
        )

    @staticmethod
    def read_pkg_cache():
        store_cache_json_file_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH

        if not store_cache_json_file_path.exists():
            log.log_debug(
                f"Skipping {store_cache_json_file_path.name.upper()} read. File not found"
            )
            return Output(Status.NOT_FOUND, {})

        try:
            data = CACHE_ADAPTER.validate_json(
                store_cache_json_file_path.read_text("utf-8")
            )
        except (OSError, ValueError, ValidationError) as e:
            log.log_error(f"Failed to read {store_cache_json_file_path.name}: {e}")
            return Output(Status.ERROR, {})

        return Output(Status.OK, data)

    @staticmethod
    def write_pkg_cache(
        path: Path | None = None, cached: dict[str, CacheSection] | None = None
    ):
        store_cache_path = path or Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        pkg_dir_path = Globals.PATHS.PKG_DIR_PATH

        if not pkg_dir_path.exists():
            log.log_debug(
                f"Skipping {pkg_dir_path.name.upper()} scan. Directory not found"
            )
            return Output(Status.NOT_FOUND, {})

        cache = {section.name: CacheSection() for section in CacheUtils._SECTIONS}
        valid_content_ids: set[str] = set()
        if cached is None:
            cached = CacheUtils.read_pkg_cache().content or {}
        else:
            cached = cached or {}
        cached_index_by_section = CacheUtils._cached_index_by_section(cached)

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
                    log.log_warn(f"Failed to stat {pkg_path.name}: {exc}")
                    continue

                section_cache = cache[section.name]
                section_cache.meta.count += 1
                section_cache.meta.total_size += int(stat.st_size)
                section_cache.meta.latest_mtime = max(
                    section_cache.meta.latest_mtime, int(stat.st_mtime_ns)
                )
                if section.name == CacheUtils._MEDIA_SECTION:
                    media_key = pkg_path.stem
                    content_id = CacheUtils._content_id_from_media_key(media_key)
                    if not content_id or content_id not in valid_content_ids:
                        continue
                    cache_key = media_key
                    cache_value = CacheUtils._cache_value(
                        stat.st_size, stat.st_mtime_ns, pkg_path.name
                    )
                else:
                    size_str = str(stat.st_size)
                    mtime_str = str(stat.st_mtime_ns)
                    cached_index = cached_index_by_section.get(section.name) or {}
                    cached_entry = cached_index.get(pkg_path.name)
                    if (
                        cached_entry
                        and cached_entry[1] == size_str
                        and cached_entry[2] == mtime_str
                    ):
                        cache_key = cached_entry[0] or pkg_path.stem
                        if cached_entry[0] and CacheUtils._is_content_id(
                            cached_entry[0]
                        ):
                            valid_content_ids.add(cached_entry[0])
                    else:
                        # Keep cache generation lightweight: avoid calling pkgtool here.
                        cache_key = pkg_path.stem
                        if CacheUtils._is_content_id(cache_key):
                            valid_content_ids.add(cache_key)
                    cache_value = CacheUtils._cache_value(
                        int(size_str), int(mtime_str), pkg_path.name
                    )
                section_cache.content[cache_key] = cache_value

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
    def compare_pkg_cache() -> Output[dict]:
        store_cache_path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        temp_path = store_cache_path.with_suffix(".tmp")

        cached_output = CacheUtils.read_pkg_cache()
        cached = cached_output.content or {}
        current_output = CacheUtils.write_pkg_cache(temp_path, cached)

        current = current_output.content or {}

        current_dump = CACHE_ADAPTER.dump_python(current)
        cached_dump = CACHE_ADAPTER.dump_python(cached)
        has_changes = current_dump != cached_dump

        added = {}
        removed = {}
        updated = {}
        current_files = {}
        changed_sections = []
        summary_lines = []

        if has_changes:
            for section in CacheUtils._SECTIONS:
                section_name = section.name
                current_section = current.get(section_name, CacheSection())
                cached_section = cached.get(section_name, CacheSection())
                current_meta = current_section.meta
                cached_meta = cached_section.meta

                section_added, section_removed, section_updated = (
                    CacheUtils._section_changes(current_section, cached_section)
                )
                added[section_name] = section_added
                removed[section_name] = section_removed
                updated[section_name] = section_updated

                if section_name != CacheUtils._MEDIA_SECTION:
                    current_files[section_name] = CacheUtils._current_file_map(
                        current_section.content
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
                    summary = CacheUtils._section_summary(
                        section_name,
                        added_count,
                        updated_count,
                        removed_count,
                    )
                    summary_lines.append(summary)

        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError as exc:
            log.log_warn(f"Failed to remove temp cache file: {exc}")
            return Output(Status.ERROR, None)

        if not has_changes:
            return Output(Status.SKIP, None)

        if summary_lines:
            log.log_info("Changes summary: " + ", ".join(summary_lines))

        return Output(
            Status.OK,
            {
                "added": added,
                "updated": updated,
                "removed": removed,
                "current_files": current_files,
                "current_cache": current,
                "changed": sorted(changed_sections),
            },
        )


CacheUtils = CacheUtils()
