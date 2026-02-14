import time
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


class Watcher:
    _MEDIA_SUFFIXES = ("_icon0", "_pic0", "_pic1")

    def __init__(self):
        self._interval = max(1, Globals.ENVS.WATCHER_PERIODIC_SCAN_SECONDS)

    def _content_id_from_media(self, name: str) -> str | None:
        base = name[:-4] if name.lower().endswith(".png") else name
        for suffix in self._MEDIA_SUFFIXES:
            if base.endswith(suffix):
                return base[: -len(suffix)]
        return None

    def _pkgs_from_media_changes(self, changes: dict) -> list[Path]:
        media_changes = []
        for key in ("removed",):
            section_changes = changes.get(key, {})
            media_changes.extend(section_changes.get("_media", []) or [])

        if not media_changes:
            return []

        pkgs = []
        for media_name in media_changes:
            content_id = self._content_id_from_media(media_name)
            if not content_id:
                continue
            for section in Section.ALL:
                if section.name == "_media":
                    continue
                pkg_path = section.path / f"{content_id}.pkg"
                if pkg_path.exists():
                    pkgs.append(pkg_path)
                    break
        return pkgs

    def _run_cycle(self) -> None:
        cache_output = CacheUtils.compare_pkg_cache()

        if cache_output.status == Status.SKIP:
            if not Globals.ENVS.FPGKI_FORMAT_ENABLED:
                log.log_info("No changes detected.")
                return
            cached = CacheUtils.read_pkg_cache().content or {}
            sections_with_content = []
            for section in Section.ALL:
                if section.name == "_media":
                    continue
                section_cache = cached.get(section.name)
                if section_cache and section_cache.content:
                    sections_with_content.append(section.name)

            if not sections_with_content:
                log.log_info("No changes detected.")
                return

            missing_fpkgi = False
            for section_name in sections_with_content:
                json_path = Globals.PATHS.DATA_DIR_PATH / f"{section_name}.json"
                if not json_path.exists():
                    missing_fpkgi = True
                    break

            if not missing_fpkgi:
                log.log_info("No changes detected.")
                return

            current_files = {}
            section_by_name = {section.name: section for section in Section.ALL}

            for section in Section.ALL:
                if section.name == "_media":
                    continue
                file_map = {}
                section_cache = cached.get(section.name)
                if section_cache and section_cache.content:
                    for key, value in section_cache.content.items():
                        parts = value.split("|", 2)
                        if len(parts) >= 3 and parts[2]:
                            filename = parts[2]
                        else:
                            filename = f"{key}.pkg"
                        file_map[key] = filename
                else:
                    section_entry = section_by_name.get(section.name)
                    if section_entry and section_entry.path.exists():
                        for pkg_path in section_entry.path.iterdir():
                            if not section_entry.accepts(pkg_path):
                                continue
                            file_map[pkg_path.stem] = pkg_path.name

                if file_map:
                    current_files[section.name] = file_map

            if not current_files:
                log.log_info("No changes detected.")
                return

            changes = {
                "changed": list(current_files.keys()),
                "added": {
                    name: list((current_files.get(name) or {}).keys())
                    for name in current_files
                },
                "updated": {},
                "removed": {},
                "current_files": current_files,
                "current_cache": cached,
            }
        else:
            changes = cache_output.content or {}

        changed_sections = changes.get("changed") or []
        changed_section_set = set(changed_sections)

        removed_by_section = changes.get("removed") or {}
        added_by_section = changes.get("added") or {}
        updated_by_section = changes.get("updated") or {}
        current_files = changes.get("current_files") or {}
        section_by_name = {section.name: section for section in Section.ALL}

        current_content_ids = set()
        for section_name, file_map in current_files.items():
            if section_name == "_media":
                continue
            current_content_ids.update((file_map or {}).keys())

        removed_content_ids = []
        for section_name, content_ids in removed_by_section.items():
            if section_name == "_media":
                continue
            for content_id in content_ids or []:
                if content_id and content_id not in current_content_ids:
                    removed_content_ids.append(content_id)

        if removed_content_ids:
            unique_ids = sorted(set(removed_content_ids))
            delete_result = DBUtils.delete_by_content_ids(unique_ids)
            if delete_result.status is Status.ERROR:
                log.log_error("Failed to delete removed PKGs from STORE.DB")

            if Globals.ENVS.FPGKI_FORMAT_ENABLED:
                fpkgi_delete = FPKGIUtils.delete_by_content_ids(unique_ids)
                if fpkgi_delete.status is Status.ERROR:
                    log.log_error("Failed to delete removed PKGs from FPKGI JSON")

            media_dir = Globals.PATHS.MEDIA_DIR_PATH
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

        scanned_pkgs = []
        for section_name in changed_sections:
            if section_name == "_media":
                continue
            section = section_by_name.get(section_name)
            if not section:
                continue
            keys = []
            keys.extend(added_by_section.get(section_name, []) or [])
            keys.extend(updated_by_section.get(section_name, []) or [])
            if not keys:
                continue
            file_map = current_files.get(section_name) or {}
            for key in keys:
                filename = file_map.get(key) or f"{key}.pkg"
                scanned_pkgs.append(section.path / filename)

        scanned_pkgs.extend(self._pkgs_from_media_changes(changes))

        if scanned_pkgs:
            seen = set()
            scanned_pkgs = [
                pkg
                for pkg in scanned_pkgs
                if not (str(pkg) in seen or seen.add(str(pkg)))
            ]
        extracted_pkgs = []
        for pkg_path in scanned_pkgs:
            validation = PkgUtils.validate(pkg_path)
            if validation.status is not Status.OK:
                FileUtils.move_to_error(
                    pkg_path,
                    Globals.PATHS.ERRORS_DIR_PATH,
                    "validation_failed",
                )
                continue

            extract_output = PkgUtils.extract_pkg_data(pkg_path)

            if extract_output.status is not Status.OK or not extract_output.content:
                continue

            param_sfo = extract_output.content
            pkg = PKG(
                title=param_sfo.data[ParamSFOKey.TITLE],
                title_id=param_sfo.data[ParamSFOKey.TITLE_ID],
                content_id=param_sfo.data[ParamSFOKey.CONTENT_ID],
                category=param_sfo.data[ParamSFOKey.CATEGORY],
                version=param_sfo.data[ParamSFOKey.VERSION],
                pubtoolinfo=param_sfo.data[ParamSFOKey.PUBTOOLINFO],
                pkg_path=pkg_path,
            )

            if pkg_path.parent.name in changed_section_set:

                target_path = AutoOrganizer.run(pkg)

                if not target_path:
                    FileUtils.move_to_error(
                        pkg_path,
                        Globals.PATHS.ERRORS_DIR_PATH,
                        "organizer_failed",
                    )
                    continue
                pkg.pkg_path = target_path
                pkg_path = target_path

            media_output = PkgUtils.extract_pkg_medias(pkg_path, pkg.content_id)

            if media_output.status is not Status.OK or not media_output.content:
                continue

            build_output = PkgUtils.build_pkg(pkg_path, param_sfo, media_output.content)

            if build_output.status is not Status.OK:
                continue

            extracted_pkgs.append(build_output.content)

        upsert_result = DBUtils.upsert(extracted_pkgs)
        if Globals.ENVS.FPGKI_FORMAT_ENABLED:
            fpkgi_result = FPKGIUtils.upsert(extracted_pkgs)
        else:
            fpkgi_result = Output(Status.SKIP, "FPKGI disabled")

        if upsert_result.status in (Status.OK, Status.SKIP) and fpkgi_result.status in (
            Status.OK,
            Status.SKIP,
        ):
            current_cache = changes.get("current_cache") or None
            if current_cache is not None:
                CacheUtils.write_pkg_cache(cached=current_cache)
            else:
                CacheUtils.write_pkg_cache()
            return

        if upsert_result.status is Status.ERROR:
            log.log_error("Store DB update failed. Cache not updated.")
        if fpkgi_result.status is Status.ERROR:
            log.log_error("FPKGI JSON update failed. Cache not updated.")

    def start(self) -> None:
        log.log_info(f"Watcher started (interval: {self._interval}s)")
        while True:
            started_at = time.monotonic()
            try:
                self._run_cycle()
            except Exception as exc:
                log.log_error(f"Watcher cycle failed: {exc}")
            elapsed = time.monotonic() - started_at
            time.sleep(max(0.0, self._interval - elapsed))
