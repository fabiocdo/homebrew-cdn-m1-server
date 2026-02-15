import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from hb_store_m1.models.globals import Globals


class URLUtils:
    _PS4_STOREDATA_ROOT = "/user/app/NPXS39041/storedata"
    _CACHE_KEY_SANITIZE = re.compile(r"[^A-Z0-9._-]")
    _APP_TYPE_TO_SECTION = {
        "app": "app",
        "dlc": "dlc",
        "game": "game",
        "patch": "update",
        "update": "update",
        "save": "save",
        "unknown": "unknown",
    }
    _APP_TYPE_TO_CLIENT_LABEL = {
        "app": "App",
        "dlc": "DLC",
        "game": "Game",
        "patch": "Patch",
        "update": "Patch",
        "save": "Other",
        "unknown": "Unknown",
        "other": "Other",
        "theme": "Theme",
        "media": "Media",
    }
    _CONTENT_ID_PATTERN = re.compile(
        r"^[A-Z]{2}[A-Z0-9]{4}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}$"
    )

    @staticmethod
    def _string_value(value: str | Path | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_slashes(path: str) -> str:
        return path.replace("\\", "/")

    @staticmethod
    def _path_from_url_or_path(value: str | Path | None) -> str | None:
        raw_value = URLUtils._string_value(value)
        if not raw_value:
            return None

        parsed = urlparse(raw_value)
        if parsed.scheme or parsed.netloc:
            path = parsed.path or ""
        else:
            path = raw_value

        path = URLUtils._normalize_slashes(path.strip())
        if not path:
            return None
        return path

    @staticmethod
    def normalize_public_path(value: str | Path | None) -> str | None:
        path = URLUtils._path_from_url_or_path(value)
        if not path:
            return None

        if path.startswith("/app/data/pkg/"):
            return path.replace("/app/data", "", 1)

        pkg_idx = path.find("/pkg/")
        if pkg_idx >= 0:
            return path[pkg_idx:]

        try:
            candidate = Path(path).resolve()
            pkg_root = Globals.PATHS.PKG_DIR_PATH.resolve()
            if candidate == pkg_root:
                return "/pkg"
            if pkg_root in candidate.parents:
                relative = candidate.relative_to(pkg_root).as_posix()
                return f"/pkg/{relative}" if relative else "/pkg"
        except Exception:
            pass

        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def to_public_url(value: str | Path | None) -> str | None:
        public_path = URLUtils.normalize_public_path(value)
        if not public_path:
            return None
        return urljoin(Globals.ENVS.SERVER_URL, public_path)

    @staticmethod
    def _is_content_id(value: str | None) -> bool:
        return bool(URLUtils._CONTENT_ID_PATTERN.match((value or "").strip().upper()))

    @staticmethod
    def normalize_app_type_section(app_type: str | None) -> str | None:
        key = (app_type or "").strip().lower()
        if not key:
            return None
        return URLUtils._APP_TYPE_TO_SECTION.get(key)

    @staticmethod
    def to_client_app_type(app_type: str | None) -> str:
        key = (app_type or "").strip().lower()
        if not key:
            return "Unknown"
        return URLUtils._APP_TYPE_TO_CLIENT_LABEL.get(key, "Unknown")

    @staticmethod
    def canonical_pkg_url(
        content_id: str | None, app_type: str | None, fallback: str | Path | None = None
    ) -> str | None:
        content = (content_id or "").strip().upper()
        section = URLUtils.normalize_app_type_section(app_type)

        if section and URLUtils._is_content_id(content):
            return urljoin(Globals.ENVS.SERVER_URL, f"/pkg/{section}/{content}.pkg")

        return URLUtils.to_public_url(fallback)

    @staticmethod
    def canonical_media_url(
        content_id: str | None,
        media_suffix: str,
        fallback: str | Path | None = None,
    ) -> str | None:
        content = (content_id or "").strip().upper()
        suffix = (media_suffix or "").strip().lower()
        if URLUtils._is_content_id(content) and suffix in {"icon0", "pic0", "pic1"}:
            return urljoin(
                Globals.ENVS.SERVER_URL,
                f"/pkg/_media/{content}_{suffix}.png",
            )
        return URLUtils.to_public_url(fallback)

    @staticmethod
    def ps4_store_icon_cache_path(content_id: str | None) -> str | None:
        content = (content_id or "").strip().upper()
        if not content:
            return None
        safe_key = URLUtils._CACHE_KEY_SANITIZE.sub("_", content).strip("._-")
        if not safe_key:
            return None
        return f"{URLUtils._PS4_STOREDATA_ROOT}/{safe_key}_icon0.png"
