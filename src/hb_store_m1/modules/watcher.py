import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import ParamSFOKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.section import Section
from hb_store_m1.modules.auto_organizer import AutoOrganizer
from hb_store_m1.utils.cache_utils import CacheUtils
from hb_store_m1.utils.db_utils import DBUtils
from hb_store_m1.utils.file_utils import FileUtils
from hb_store_m1.utils.fpkgi_utils import FPKGIUtils
from hb_store_m1.utils.log_utils import LogUtils
from hb_store_m1.utils.pkg_utils import PkgUtils

log = LogUtils(LogModule.WATCHER)


@dataclass(slots=True)
class WatchChanges:
    changed: list[str] = field(default_factory=list)
    added: dict[str, list[str]] = field(default_factory=dict)
    updated: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)
    current_files: dict[str, dict[str, str]] = field(default_factory=dict)
    current_cache: dict | None = None
    cache_missing: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "WatchChanges":
        raw = data or {}
        return cls(
            changed=list(raw.get("changed") or []),
            added={
                key: list(value or [])
                for key, value in (raw.get("added") or {}).items()
            },
            updated={
                key: list(value or [])
                for key, value in (raw.get("updated") or {}).items()
            },
            removed={
                key: list(value or [])
                for key, value in (raw.get("removed") or {}).items()
            },
            current_files={
                key: dict(value or {})
                for key, value in (raw.get("current_files") or {}).items()
            },
            current_cache=raw.get("current_cache"),
        )


class Watcher:
    _MEDIA_SECTION_NAME = "_media"
    _MEDIA_SUFFIXES = ("_icon0", "_pic0", "_pic1")
    _CONTENT_ID_PATTERN = re.compile(
        r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$"
    )

    def __init__(
        self,
        cache_utils=None,
        db_utils=None,
        file_utils=None,
        fpkgi_utils=None,
        pkg_utils=None,
        auto_organizer=None,
        envs=None,
        paths=None,
    ):
        self._cache_utils = cache_utils or CacheUtils
        self._db_utils = db_utils or DBUtils
        self._file_utils = file_utils or FileUtils
        self._fpkgi_utils = fpkgi_utils or FPKGIUtils
        self._pkg_utils = pkg_utils or PkgUtils
        self._auto_organizer = auto_organizer or AutoOrganizer
        self._envs = envs or Globals.ENVS
        self._paths = paths or Globals.PATHS
        self._interval = max(1, self._envs.WATCHER_PERIODIC_SCAN_SECONDS)

    @staticmethod
    def _iter_pkg_sections():
        for section in Section.ALL:
            if section.name != Watcher._MEDIA_SECTION_NAME:
                yield section

    @staticmethod
    def _section_by_name() -> dict[str, object]:
        return {section.name: section for section in Section.ALL}

    def _content_id_from_media(self, name: str) -> str | None:
        base = name[:-4] if name.lower().endswith(".png") else name
        for suffix in self._MEDIA_SUFFIXES:
            if base.endswith(suffix):
                return base[: -len(suffix)]
        return None

    def _pkgs_from_media_changes(
        self, changes: dict[str, list[str]] | dict
    ) -> list[Path]:
        removed_by_section = changes.get("removed", changes)
        media_changes = removed_by_section.get(self._MEDIA_SECTION_NAME, []) or []

        if not media_changes:
            return []

        pkgs = []
        for media_name in media_changes:
            content_id = self._content_id_from_media(media_name)
            if not content_id:
                continue
            for section in self._iter_pkg_sections():
                pkg_path = section.path / f"{content_id}.pkg"
                if pkg_path.exists():
                    pkgs.append(pkg_path)
                    break
        return pkgs

    @staticmethod
    def _filename_from_cache_entry(key: str, value: str) -> str:
        parts = value.split("|", 2)
        if len(parts) >= 3 and parts[2]:
            return parts[2]
        return f"{key}.pkg"

    @staticmethod
    def _log_no_changes() -> None:
        log.log_info("No changes detected.")

    def _sections_with_cached_content(self, cached: dict) -> list[str]:
        sections_with_content = []
        for section in self._iter_pkg_sections():
            section_cache = cached.get(section.name)
            if section_cache and section_cache.content:
                sections_with_content.append(section.name)
        return sections_with_content

    def _has_missing_fpkgi_json(self, sections: list[str]) -> bool:
        for section_name in sections:
            json_path = self._paths.DATA_DIR_PATH / f"{section_name}.json"
            if not json_path.exists():
                return True
        return False

    def _file_map_from_cache(self, section_cache) -> dict[str, str]:
        if not section_cache or not section_cache.content:
            return {}
        return {
            key: self._filename_from_cache_entry(key, value)
            for key, value in section_cache.content.items()
        }

    @staticmethod
    def _file_map_from_disk(section) -> dict[str, str]:
        if not section.path.exists():
            return {}
        file_map = {}
        for pkg_path in section.path.iterdir():
            if not section.accepts(pkg_path):
                continue
            file_map[pkg_path.stem] = pkg_path.name
        return file_map

    def _build_current_files(self, cached: dict) -> dict[str, dict[str, str]]:
        current_files: dict[str, dict[str, str]] = {}
        for section in self._iter_pkg_sections():
            file_map = self._file_map_from_cache(cached.get(section.name))
            if not file_map:
                file_map = self._file_map_from_disk(section)
            if file_map:
                current_files[section.name] = file_map
        return current_files

    def _build_changes_for_missing_fpkgi(self) -> WatchChanges | None:
        if not self._envs.FPGKI_FORMAT_ENABLED:
            self._log_no_changes()
            return None

        cached = self._cache_utils.read_pkg_cache().content or {}
        sections_with_content = self._sections_with_cached_content(cached)
        if not sections_with_content:
            self._log_no_changes()
            return None

        if not self._has_missing_fpkgi_json(sections_with_content):
            self._log_no_changes()
            return None

        current_files = self._build_current_files(cached)
        if not current_files:
            self._log_no_changes()
            return None

        return WatchChanges(
            changed=list(current_files.keys()),
            added={
                section_name: list((current_files.get(section_name) or {}).keys())
                for section_name in current_files
            },
            updated={},
            removed={},
            current_files=current_files,
            current_cache=cached,
        )

    def _load_changes(self) -> WatchChanges | None:
        cache_read_output = self._cache_utils.read_pkg_cache()
        cache_missing = cache_read_output.status is Status.NOT_FOUND

        cache_output = self._cache_utils.compare_pkg_cache()
        if cache_output.status is Status.SKIP:
            return self._build_changes_for_missing_fpkgi()
        changes = WatchChanges.from_dict(cache_output.content)
        changes.cache_missing = cache_missing
        return changes

    @staticmethod
    def _collect_current_content_ids(
        current_files: dict[str, dict[str, str]],
    ) -> set[str]:
        current_content_ids = set()
        for file_map in current_files.values():
            current_content_ids.update((file_map or {}).keys())
        return current_content_ids

    def _collect_removed_content_ids(self, changes: WatchChanges) -> list[str]:
        current_content_ids = self._collect_current_content_ids(changes.current_files)
        removed_content_ids = []
        for section_name, content_ids in changes.removed.items():
            if section_name == self._MEDIA_SECTION_NAME:
                continue
            for content_id in content_ids or []:
                if content_id and content_id not in current_content_ids:
                    removed_content_ids.append(content_id)
        return removed_content_ids

    def _collect_removed_ids_from_db_snapshot(
        self, current_content_ids: set[str]
    ) -> list[str]:
        db_content_ids_output = self._db_utils.select_content_ids()
        if db_content_ids_output.status not in (Status.OK, Status.SKIP):
            return []
        db_content_ids = db_content_ids_output.content or []
        return [
            content_id
            for content_id in db_content_ids
            if content_id not in current_content_ids
        ]

    def _handle_removed_content_ids(self, removed_content_ids: list[str]) -> None:
        if not removed_content_ids:
            return

        unique_ids = sorted(set(removed_content_ids))
        delete_result = self._db_utils.delete_by_content_ids(unique_ids)
        if delete_result.status is Status.ERROR:
            log.log_error("Failed to delete removed PKGs from STORE.DB")

        if self._envs.FPGKI_FORMAT_ENABLED:
            fpkgi_delete = self._fpkgi_utils.delete_by_content_ids(unique_ids)
            if fpkgi_delete.status is Status.ERROR:
                log.log_error("Failed to delete removed PKGs from FPKGI JSON")

        media_dir = self._paths.MEDIA_DIR_PATH
        for content_id in unique_ids:
            for suffix in self._MEDIA_SUFFIXES:
                media_path = media_dir / f"{content_id}{suffix}.png"
                try:
                    if media_path.exists():
                        media_path.unlink()
                except OSError as exc:
                    log.log_warn(
                        f"Failed to remove media file {media_path.name}: {exc}"
                    )

    def _collect_scanned_pkgs(self, changes: WatchChanges) -> list[Path]:
        scanned_pkgs: list[Path] = []
        section_by_name = self._section_by_name()

        for section_name in changes.changed:
            if section_name == self._MEDIA_SECTION_NAME:
                continue
            section = section_by_name.get(section_name)
            if not section:
                continue
            keys = []
            keys.extend(changes.added.get(section_name, []) or [])
            keys.extend(changes.updated.get(section_name, []) or [])
            if not keys:
                continue
            file_map = changes.current_files.get(section_name) or {}
            for key in keys:
                filename = file_map.get(key) or f"{key}.pkg"
                scanned_pkgs.append(section.path / filename)

        scanned_pkgs.extend(self._pkgs_from_media_changes(changes.removed))
        return list(dict.fromkeys(scanned_pkgs))

    @classmethod
    def _is_canonical_pkg_filename(cls, pkg_path: Path) -> bool:
        return bool(cls._CONTENT_ID_PATTERN.match(pkg_path.stem))

    def _collect_non_canonical_pkgs(self) -> list[Path]:
        non_canonical_pkgs: list[Path] = []
        for section in self._iter_pkg_sections():
            if not section.path.exists():
                continue
            for pkg_path in section.path.iterdir():
                if not section.accepts(pkg_path):
                    continue
                if not self._is_canonical_pkg_filename(pkg_path):
                    non_canonical_pkgs.append(pkg_path)
        return non_canonical_pkgs

    def _has_pkg_for_content_id(self, content_id: str) -> bool:
        for section in self._iter_pkg_sections():
            if (section.path / f"{content_id}.pkg").exists():
                return True
        return False

    def _normalize_media_files(self) -> None:
        media_dir = self._paths.MEDIA_DIR_PATH
        if not media_dir.exists():
            return

        for media_path in list(media_dir.iterdir()):
            if not Section.MEDIA.accepts(media_path):
                continue

            content_id = self._content_id_from_media(media_path.name)
            if not content_id:
                self._file_utils.move_to_error(
                    media_path,
                    self._paths.ERRORS_DIR_PATH,
                    "invalid_media_name",
                )
                continue

            if not self._has_pkg_for_content_id(content_id):
                self._file_utils.move_to_error(
                    media_path,
                    self._paths.ERRORS_DIR_PATH,
                    "orphan_media",
                )

    @staticmethod
    def _build_pkg_model(pkg_path: Path, param_sfo) -> PKG:
        return PKG(
            title=param_sfo.data[ParamSFOKey.TITLE],
            title_id=param_sfo.data[ParamSFOKey.TITLE_ID],
            content_id=param_sfo.data[ParamSFOKey.CONTENT_ID],
            category=param_sfo.data[ParamSFOKey.CATEGORY],
            version=param_sfo.data[ParamSFOKey.VERSION],
            pubtoolinfo=param_sfo.data[ParamSFOKey.PUBTOOLINFO],
            pkg_path=pkg_path,
        )

    def _process_pkg(self, pkg_path: Path):
        validation = self._pkg_utils.validate(pkg_path)
        if validation.status not in (Status.OK, Status.WARN):
            self._file_utils.move_to_error(
                pkg_path,
                self._paths.ERRORS_DIR_PATH,
                "validation_failed",
            )
            return None

        extract_output = self._pkg_utils.extract_pkg_data(pkg_path)
        if extract_output.status is not Status.OK or not extract_output.content:
            self._file_utils.move_to_error(
                pkg_path,
                self._paths.ERRORS_DIR_PATH,
                "extract_data_failed",
            )
            return None

        param_sfo = extract_output.content
        pkg = self._build_pkg_model(pkg_path, param_sfo)

        # Always normalize/move by content_id to guarantee canonical PKG naming.
        target_path = self._auto_organizer.run(pkg)
        if not target_path:
            self._file_utils.move_to_error(
                pkg_path,
                self._paths.ERRORS_DIR_PATH,
                "organizer_failed",
            )
            return None
        pkg.pkg_path = target_path
        pkg_path = target_path

        media_output = self._pkg_utils.extract_pkg_medias(pkg_path, pkg.content_id)
        if media_output.status is not Status.OK or not media_output.content:
            self._file_utils.move_to_error(
                pkg_path,
                self._paths.ERRORS_DIR_PATH,
                "extract_medias_failed",
            )
            return None

        build_output = self._pkg_utils.build_pkg(
            pkg_path, param_sfo, media_output.content
        )
        if build_output.status is not Status.OK:
            self._file_utils.move_to_error(
                pkg_path,
                self._paths.ERRORS_DIR_PATH,
                "build_failed",
            )
            return None

        return build_output.content

    def _persist_results(
        self, extracted_pkgs: list, current_cache: dict | None
    ) -> None:
        upsert_result = self._db_utils.upsert(extracted_pkgs)
        if self._envs.FPGKI_FORMAT_ENABLED:
            fpkgi_result = self._fpkgi_utils.upsert(extracted_pkgs)
        else:
            fpkgi_result = Output(Status.SKIP, "FPKGI disabled")

        if upsert_result.status in (Status.OK, Status.SKIP) and fpkgi_result.status in (
            Status.OK,
            Status.SKIP,
        ):
            if current_cache is not None:
                self._cache_utils.write_pkg_cache(cached=current_cache)
            else:
                self._cache_utils.write_pkg_cache()
            return

        if upsert_result.status is Status.ERROR:
            log.log_error("Store DB update failed. Cache not updated.")
        if fpkgi_result.status is Status.ERROR:
            log.log_error("FPKGI JSON update failed. Cache not updated.")

    def _run_cycle(self) -> None:
        changes = self._load_changes()
        if not changes:
            extracted_pkgs = []
            scanned_pkgs = self._collect_non_canonical_pkgs()
            for pkg_path in scanned_pkgs:
                built_pkg = self._process_pkg(pkg_path)
                if built_pkg is not None:
                    extracted_pkgs.append(built_pkg)
            if scanned_pkgs:
                self._persist_results(extracted_pkgs, None)
            self._normalize_media_files()
            return

        removed_content_ids = self._collect_removed_content_ids(changes)
        if changes.cache_missing:
            current_content_ids = self._collect_current_content_ids(
                changes.current_files
            )
            removed_content_ids.extend(
                self._collect_removed_ids_from_db_snapshot(current_content_ids)
            )
        self._handle_removed_content_ids(removed_content_ids)

        scanned_pkgs = self._collect_scanned_pkgs(changes)
        extracted_pkgs = []
        for pkg_path in scanned_pkgs:
            built_pkg = self._process_pkg(pkg_path)
            if built_pkg is not None:
                extracted_pkgs.append(built_pkg)

        self._persist_results(extracted_pkgs, changes.current_cache)
        self._normalize_media_files()

    def start(self) -> None:
        log.log_info(f"Watcher started (interval: {self._interval}s)")
        while True:
            started_at = time.monotonic()
            try:
                self._run_cycle()
            except Exception as exc:
                log.log_error(f"Watcher cycle failed: {exc}\n{traceback.format_exc()}")
            elapsed = time.monotonic() - started_at
            time.sleep(max(0.0, self._interval - elapsed))
