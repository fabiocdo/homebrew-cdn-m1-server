import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from hb_store_m1.models.fpkgi import FPKGI
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.pkg import PKG, AppType
from hb_store_m1.utils.log_utils import LogUtils
from hb_store_m1.utils.url_utils import URLUtils

log = LogUtils(LogModule.FPKGI_UTIL)


class FPKGIUtils:
    _CONTENT_ID_PATTERN = re.compile(
        r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$"
    )
    _RELEASE_DATE_PATTERN = re.compile(
        r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$"
    )
    _REGION_BY_PREFIX = {
        "UP": "USA",
        "EP": "EUR",
        "JP": "JAP",
        "HP": "ASIA",
        "AP": "ASIA",
        "KP": "ASIA",
    }
    _JSON_STEM_BY_APP_TYPE = {
        "app": "APPS",
        "demo": "DEMOS",
        "dlc": "DLC",
        "emulator": "EMULATORS",
        "game": "GAMES",
        "homebrew": "HOMEBREW",
        "ps1": "PS1",
        "ps2": "PS2",
        "ps5": "PS5",
        "psp": "PSP",
        "theme": "THEMES",
        "update": "UPDATES",
        "save": "SAVES",
        "unknown": "UNKNOWN",
    }

    @staticmethod
    def _normalized_app_type(app_type: str | None) -> str:
        return (app_type or "unknown").strip().lower() or "unknown"

    @staticmethod
    def _json_stem_for_app_type(app_type: str) -> str:
        normalized = FPKGIUtils._normalized_app_type(app_type)
        return FPKGIUtils._JSON_STEM_BY_APP_TYPE.get(normalized, normalized.upper())

    @staticmethod
    def _json_path(app_type: str) -> Path:
        stem = FPKGIUtils._json_stem_for_app_type(app_type)
        return Globals.PATHS.DATA_DIR_PATH / f"{stem}.json"

    @staticmethod
    def _legacy_json_path(app_type: str) -> Path:
        normalized = FPKGIUtils._normalized_app_type(app_type)
        return Globals.PATHS.DATA_DIR_PATH / f"{normalized}.json"

    @staticmethod
    def json_path_for_app_type(app_type: str) -> Path:
        return FPKGIUtils._json_path(app_type)

    @staticmethod
    def _read_entries_for_app_type(
        app_type: str,
    ) -> tuple[Path, Path, dict[str, dict[str, object]] | None, bool]:
        json_path = FPKGIUtils._json_path(app_type)
        legacy_path = FPKGIUtils._legacy_json_path(app_type)
        has_legacy_file = legacy_path.exists() and legacy_path != json_path

        if json_path.exists():
            entries, migrated = FPKGIUtils._read_json(json_path, app_type)
            return json_path, legacy_path, entries, (migrated or has_legacy_file)

        if legacy_path.exists():
            entries, migrated = FPKGIUtils._read_json(legacy_path, app_type)
            return (
                json_path,
                legacy_path,
                entries,
                migrated or (legacy_path != json_path),
            )

        return json_path, legacy_path, {}, False

    @staticmethod
    def _cleanup_legacy_json(json_path: Path, legacy_path: Path) -> None:
        if legacy_path == json_path or not legacy_path.exists():
            return
        try:
            legacy_path.unlink()
        except OSError as exc:
            log.log_warn(f"Failed to remove legacy FPKGI file {legacy_path.name}: {exc}")

    @staticmethod
    def _entry_md5(values_by_column: dict[str, object]) -> str:
        columns = [col.value for col in FPKGI.Column]
        payload = json.dumps(
            [values_by_column.get(name) for name in columns],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.md5(payload).hexdigest()

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _to_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_region(value: object) -> str | None:
        region = FPKGIUtils._string_or_none(value)
        if not region:
            return None
        region_upper = region.upper()
        if region_upper in {"USA", "EUR", "JAP", "ASIA"}:
            return region_upper
        return None

    @staticmethod
    def _normalize_release(value: object) -> str | None:
        text = FPKGIUtils._string_or_none(value)
        if not text:
            return None
        match = FPKGIUtils._RELEASE_DATE_PATTERN.match(text)
        if not match:
            return text
        return f"{match.group('month')}-{match.group('day')}-{match.group('year')}"

    @staticmethod
    def _normalize_metadata(values: dict[str, object]) -> dict[str, object]:
        return {
            FPKGI.Column.TITLE_ID.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.TITLE_ID.value)
            ),
            FPKGI.Column.REGION.value: FPKGIUtils._normalize_region(
                values.get(FPKGI.Column.REGION.value)
            ),
            FPKGI.Column.NAME.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.NAME.value)
            ),
            FPKGI.Column.VERSION.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.VERSION.value)
            ),
            FPKGI.Column.RELEASE.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.RELEASE.value)
            ),
            FPKGI.Column.SIZE.value: FPKGIUtils._to_int(
                values.get(FPKGI.Column.SIZE.value), 0
            ),
            FPKGI.Column.MIN_FW.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.MIN_FW.value)
            ),
            FPKGI.Column.COVER_URL.value: FPKGIUtils._string_or_none(
                values.get(FPKGI.Column.COVER_URL.value)
            ),
        }

    @staticmethod
    def _content_id_from_pkg_url(pkg_url: str | None) -> str | None:
        raw = str(pkg_url or "").strip()
        if not raw:
            return None
        parsed = urlparse(raw)
        path = parsed.path or raw
        filename = Path(path).name
        if not filename.lower().endswith(".pkg"):
            return None
        content_id = filename[:-4].upper()
        if not FPKGIUtils._CONTENT_ID_PATTERN.match(content_id):
            return None
        return content_id

    @staticmethod
    def _region_from_content_id(content_id: str | None) -> str | None:
        content = str(content_id or "").strip().upper()
        if len(content) < 2:
            return None
        return FPKGIUtils._REGION_BY_PREFIX.get(content[:2])

    @staticmethod
    def _rewrite_public_url(value: object) -> str | None:
        raw = FPKGIUtils._string_or_none(value)
        if not raw:
            return None

        parsed = urlparse(raw)
        path = parsed.path if (parsed.scheme or parsed.netloc) else raw
        path = path.replace("\\", "/").strip()
        if not path:
            return None

        if path.startswith("/app/data/pkg/"):
            public_path = path.replace("/app/data", "", 1)
        else:
            pkg_idx = path.find("/pkg/")
            if pkg_idx < 0:
                return raw
            public_path = path[pkg_idx:]

        if not public_path.startswith("/"):
            public_path = f"/{public_path}"
        return urljoin(Globals.ENVS.SERVER_URL, public_path)

    @staticmethod
    def _pkg_size(pkg: PKG) -> int:
        if pkg.size:
            return int(pkg.size)
        if not pkg.pkg_path:
            return 0
        try:
            return int(pkg.pkg_path.stat().st_size)
        except OSError:
            return 0

    @staticmethod
    def _legacy_entries_to_data(
        app_type: str, legacy_entries: list[dict[str, object]]
    ) -> dict[str, dict[str, object]]:
        data_entries: dict[str, dict[str, object]] = {}
        for legacy_entry in legacy_entries:
            if not isinstance(legacy_entry, dict):
                continue

            content_id = str(
                legacy_entry.get(FPKGI.LegacyColumn.ID.value) or ""
            ).strip().upper()
            package_url = URLUtils.canonical_pkg_url(
                content_id,
                app_type,
                legacy_entry.get(FPKGI.LegacyColumn.PACKAGE.value),
            )
            if not package_url:
                continue

            data_entries[package_url] = {
                FPKGI.Column.TITLE_ID.value: None,
                FPKGI.Column.REGION.value: FPKGIUtils._region_from_content_id(content_id),
                FPKGI.Column.NAME.value: FPKGIUtils._string_or_none(
                    legacy_entry.get(FPKGI.LegacyColumn.NAME.value)
                ),
                FPKGI.Column.VERSION.value: FPKGIUtils._string_or_none(
                    legacy_entry.get(FPKGI.LegacyColumn.VERSION.value)
                ),
                FPKGI.Column.RELEASE.value: None,
                FPKGI.Column.SIZE.value: FPKGIUtils._to_int(
                    legacy_entry.get(FPKGI.LegacyColumn.SIZE.value), 0
                ),
                FPKGI.Column.MIN_FW.value: None,
                FPKGI.Column.COVER_URL.value: URLUtils.canonical_media_url(
                    content_id,
                    "icon0",
                    legacy_entry.get(FPKGI.LegacyColumn.ICON.value),
                )
                or FPKGIUtils._rewrite_public_url(
                    legacy_entry.get(FPKGI.LegacyColumn.ICON.value)
                ),
            }
        return data_entries

    @staticmethod
    def _read_json(
        path: Path, app_type: str
    ) -> tuple[dict[str, dict[str, object]] | None, bool]:
        if not path.exists():
            return {}, False
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.log_error(f"Failed to read {path.name}: {exc}")
            return None, False

        if isinstance(data, list):
            return FPKGIUtils._legacy_entries_to_data(app_type, data), True

        if isinstance(data, dict):
            if FPKGI.Root.DATA.value in data:
                raw_entries = data.get(FPKGI.Root.DATA.value)
                if not isinstance(raw_entries, dict):
                    log.log_error(f"Invalid {path.name}. Expected DATA as object")
                    return None, False
                normalized: dict[str, dict[str, object]] = {}
                for pkg_url, metadata in raw_entries.items():
                    pkg_url_text = str(pkg_url).strip()
                    if not pkg_url_text or not isinstance(metadata, dict):
                        continue
                    normalized[pkg_url_text] = FPKGIUtils._normalize_metadata(metadata)
                return normalized, False

            if all(isinstance(value, dict) for value in data.values()):
                normalized = {
                    str(pkg_url).strip(): FPKGIUtils._normalize_metadata(metadata)
                    for pkg_url, metadata in data.items()
                    if str(pkg_url).strip()
                }
                return normalized, True

        log.log_error(f"Invalid {path.name}. Expected FPKGi JSON object")
        return None, False

    @staticmethod
    def _write_json(path: Path, entries: dict[str, dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            FPKGI.Root.DATA.value: {
                pkg_url: entries[pkg_url] for pkg_url in sorted(entries.keys())
            }
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _entry_from_pkg(pkg: PKG) -> tuple[str, dict[str, object]] | None:
        app_type = str(pkg.app_type) if pkg.app_type else "unknown"
        content_id = str(pkg.content_id or "").strip().upper()
        package_url = URLUtils.canonical_pkg_url(content_id, app_type, pkg.pkg_path)
        if not package_url:
            return None

        region = pkg.region.value if pkg.region and pkg.region.value != "UNKNOWN" else None
        metadata = {
            FPKGI.Column.TITLE_ID.value: FPKGIUtils._string_or_none(pkg.title_id),
            FPKGI.Column.REGION.value: region,
            FPKGI.Column.NAME.value: FPKGIUtils._string_or_none(pkg.title),
            FPKGI.Column.VERSION.value: FPKGIUtils._string_or_none(pkg.version),
            FPKGI.Column.RELEASE.value: FPKGIUtils._normalize_release(pkg.release_date),
            FPKGI.Column.SIZE.value: FPKGIUtils._pkg_size(pkg),
            FPKGI.Column.MIN_FW.value: None,
            FPKGI.Column.COVER_URL.value: URLUtils.canonical_media_url(
                content_id, "icon0", pkg.icon0_png_path
            ),
        }
        return package_url, metadata

    @staticmethod
    def _app_type_names() -> list[str]:
        return sorted(
            {app_type.value for app_type in AppType}
            | set(FPKGIUtils._JSON_STEM_BY_APP_TYPE.keys())
        )

    @staticmethod
    def _group_pkgs_by_app_type(pkgs: list[PKG]) -> dict[str, list[PKG]]:
        pkgs_by_type: dict[str, list[PKG]] = {}
        for pkg in pkgs:
            app_type = FPKGIUtils._normalized_app_type(
                pkg.app_type.value if pkg.app_type else "unknown"
            )
            pkgs_by_type.setdefault(app_type, []).append(pkg)
        return pkgs_by_type

    @staticmethod
    def _urls_by_content_id(
        entries: dict[str, dict[str, object]],
    ) -> dict[str, set[str]]:
        by_content_id: dict[str, set[str]] = {}
        for pkg_url in entries.keys():
            content_id = FPKGIUtils._content_id_from_pkg_url(pkg_url)
            if not content_id:
                continue
            by_content_id.setdefault(content_id, set()).add(pkg_url)
        return by_content_id

    @staticmethod
    def upsert(pkgs: list[PKG]) -> Output:
        if not pkgs:
            return Output(Status.SKIP, "Nothing to upsert")

        pkgs_by_type = FPKGIUtils._group_pkgs_by_app_type(pkgs)

        log.log_info(f"Attempting to upsert {len(pkgs)} PKGs in FPKGI JSON...")

        updated_total = 0
        skipped_total = 0
        renamed_total = 0

        for app_type, pkgs_for_type in pkgs_by_type.items():
            json_path, legacy_path, entries, migrated = FPKGIUtils._read_entries_for_app_type(
                app_type
            )
            if entries is None:
                return Output(Status.ERROR, "Failed to read FPKGI JSON")

            hash_by_url = {
                pkg_url: FPKGIUtils._entry_md5(metadata)
                for pkg_url, metadata in entries.items()
            }
            urls_by_content_id = FPKGIUtils._urls_by_content_id(entries)

            updated_for_type = 0
            for pkg in pkgs_for_type:
                pkg_entry = FPKGIUtils._entry_from_pkg(pkg)
                if not pkg_entry:
                    continue

                package_url, metadata = pkg_entry
                content_id = FPKGIUtils._content_id_from_pkg_url(package_url)
                if content_id:
                    stale_urls = {
                        stale_url
                        for stale_url in urls_by_content_id.get(content_id, set())
                        if stale_url != package_url
                    }
                    for stale_url in stale_urls:
                        entries.pop(stale_url, None)
                        hash_by_url.pop(stale_url, None)
                        urls_by_content_id[content_id].discard(stale_url)

                entry_hash = FPKGIUtils._entry_md5(metadata)
                if hash_by_url.get(package_url) == entry_hash:
                    skipped_total += 1
                    continue

                entries[package_url] = metadata
                hash_by_url[package_url] = entry_hash
                if content_id:
                    urls_by_content_id.setdefault(content_id, set()).add(package_url)
                updated_for_type += 1

            if updated_for_type or migrated:
                FPKGIUtils._write_json(json_path, entries)
                FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)
                updated_total += updated_for_type
                if migrated:
                    renamed_total += 1

        if skipped_total and updated_total == 0 and renamed_total == 0:
            log.log_info(f"Skipped {skipped_total} unchanged PKGs")
            return Output(Status.SKIP, None)

        if renamed_total:
            log.log_info(f"Renamed {renamed_total} legacy FPKGI JSON files")
        log.log_info(f"{updated_total} PKGs upserted successfully")
        return Output(Status.OK, updated_total)

    @staticmethod
    def delete_by_content_ids(content_ids: list[str]) -> Output:
        if not content_ids:
            return Output(Status.SKIP, "Nothing to delete")

        deleted_total = 0
        target_ids = set(content_ids)

        for app_type in FPKGIUtils._app_type_names():
            json_path, legacy_path, entries, migrated = FPKGIUtils._read_entries_for_app_type(
                app_type
            )
            if entries is None:
                return Output(Status.ERROR, "Failed to read FPKGI JSON")
            if not entries:
                if migrated:
                    FPKGIUtils._write_json(json_path, entries)
                    FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)
                continue

            remaining = {
                pkg_url: metadata
                for pkg_url, metadata in entries.items()
                if FPKGIUtils._content_id_from_pkg_url(pkg_url) not in target_ids
            }
            removed = len(entries) - len(remaining)
            if removed or migrated:
                FPKGIUtils._write_json(json_path, remaining)
                FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)
                deleted_total += removed

        log.log_info(f"{deleted_total} PKGs deleted successfully")
        return Output(Status.OK, deleted_total)

    @staticmethod
    def refresh_urls() -> Output:
        updated_total = 0
        app_types = FPKGIUtils._app_type_names()

        for app_type in app_types:
            json_path, legacy_path, entries, migrated = FPKGIUtils._read_entries_for_app_type(
                app_type
            )
            if entries is None:
                return Output(Status.ERROR, "Failed to read FPKGI JSON")
            if not entries:
                if migrated:
                    FPKGIUtils._write_json(json_path, entries)
                    FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)
                    updated_total += 1
                continue

            changed = migrated
            refreshed: dict[str, dict[str, object]] = {}
            for package_old, metadata_old in entries.items():
                content_id = FPKGIUtils._content_id_from_pkg_url(package_old)
                package_new = URLUtils.canonical_pkg_url(content_id, app_type, package_old)
                if package_new is None:
                    package_new = package_old
                if package_new != package_old:
                    changed = True

                metadata_new = FPKGIUtils._normalize_metadata(metadata_old)
                if metadata_new != metadata_old:
                    changed = True

                cover_old = metadata_new.get(FPKGI.Column.COVER_URL.value)
                cover_new = FPKGIUtils._rewrite_public_url(cover_old)
                if cover_new != cover_old:
                    metadata_new[FPKGI.Column.COVER_URL.value] = cover_new
                    changed = True

                if package_new in refreshed and refreshed[package_new] != metadata_new:
                    changed = True
                refreshed[package_new] = metadata_new

            if changed:
                FPKGIUtils._write_json(json_path, refreshed)
                FPKGIUtils._cleanup_legacy_json(json_path, legacy_path)
                updated_total += 1

        if updated_total:
            log.log_info(f"Refreshed URLs in {updated_total} FPKGI JSON files")
            return Output(Status.OK, updated_total)
        return Output(Status.SKIP, "URLs already up to date")


FPKGIUtils = FPKGIUtils()
