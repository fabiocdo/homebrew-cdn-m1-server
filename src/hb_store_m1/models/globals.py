import os
import tomllib
from dataclasses import dataclass
from pathlib import Path as _Path


def _pyproject_value(path: _Path, key: str, default: str = "") -> str:
    if not path.exists():
        return default
    data = tomllib.loads(path.read_text("utf-8"))
    return data.get("project", {}).get(key, default)


def _env(name: str, default, type_):
    v = os.getenv(name)
    if v is None:
        return default

    v = v.strip()

    if type_ is bool:
        vl = v.lower()
        if vl == "true":
            return True
        if vl == "false":
            return False
        raise ValueError(f"{name} must be 'true' or 'false', got {v!r}")

    if type_ is int:
        return default if v == "" else int(v)

    if type_ is str:
        return v.upper()

    if type_ is list:
        if v == "":
            if isinstance(default, list):
                return [str(p).strip().upper() for p in default if str(p).strip()]
            return [p.strip().upper() for p in str(default).split(",") if p.strip()]
        return [p.strip().upper() for p in v.split(",") if p.strip()]

    raise TypeError(f"Unsupported type {type_}")


@dataclass(frozen=True)
class _GlobalPaths:
    APP_ROOT_PATH: _Path = _Path.cwd()
    INIT_DIR_PATH: _Path = _Path.cwd() / "init"
    DATA_DIR_PATH: _Path = APP_ROOT_PATH / "data"
    CACHE_DIR_PATH: _Path = DATA_DIR_PATH / "_cache"
    ERRORS_DIR_PATH: _Path = DATA_DIR_PATH / "_errors"
    LOGS_DIR_PATH: _Path = DATA_DIR_PATH / "_logs"
    PKG_DIR_PATH: _Path = DATA_DIR_PATH / "pkg"
    MEDIA_DIR_PATH: _Path = PKG_DIR_PATH / "_media"
    APP_DIR_PATH: _Path = PKG_DIR_PATH / "app"
    GAME_DIR_PATH: _Path = PKG_DIR_PATH / "game"
    DLC_DIR_PATH: _Path = PKG_DIR_PATH / "dlc"
    UPDATE_DIR_PATH: _Path = PKG_DIR_PATH / "update"
    SAVE_DIR_PATH: _Path = PKG_DIR_PATH / "save"
    UNKNOWN_DIR_PATH: _Path = PKG_DIR_PATH / "unknown"


@dataclass(frozen=True)
class _GlobalFiles:
    paths: _GlobalPaths

    @property
    def PYPROJECT_FILE_PATH(self) -> _Path:
        return self.paths.APP_ROOT_PATH / "pyproject.toml"

    @property
    def STORE_DB_INIT_SCRIPT_FILE_PATH(self) -> _Path:
        return self.paths.INIT_DIR_PATH / "store_db.sql"

    @property
    def JSON_TEMPLATE_INIT_FILE_PATH(self) -> _Path:
        return self.paths.INIT_DIR_PATH / "json_template.json"

    @property
    def PKGTOOL_FILE_PATH(self) -> _Path:
        return self.paths.APP_ROOT_PATH / "bin" / "pkgtool"

    @property
    def INDEX_JSON_FILE_PATH(self) -> _Path:
        return self.paths.DATA_DIR_PATH / "index.json"

    @property
    def STORE_DB_FILE_PATH(self) -> _Path:
        return self.paths.DATA_DIR_PATH / "store.db"

    @property
    def INDEX_CACHE_JSON_FILE_PATH(self) -> _Path:
        return self.paths.CACHE_DIR_PATH / "index-cache.json"

    @property
    def STORE_CACHE_JSON_FILE_PATH(self) -> _Path:
        return self.paths.CACHE_DIR_PATH / "store-cache.json"

    @property
    def HOMEBREW_ELF_FILE_PATH(self) -> _Path:
        return self.paths.CACHE_DIR_PATH / "homebrew.elf"

    @property
    def HOMEBREW_ELF_SIG_FILE_PATH(self) -> _Path:
        return self.paths.CACHE_DIR_PATH / "homebrew.elf.sig"

    @property
    def REMOTE_MD5_FILE_PATH(self) -> _Path:
        return self.paths.CACHE_DIR_PATH / "remote.md5"

    @property
    def ERRORS_LOG_FILE_PATH(self) -> _Path:
        return self.paths.ERRORS_DIR_PATH / "app_errors.log"


class _GlobalEnvs:
    def __init__(self, files: _GlobalFiles):
        self.files = files

        self.SERVER_IP: str = _env("SERVER_IP", "127.0.0.1", str)
        self.SERVER_PORT: int = _env("SERVER_PORT", 80, int)
        self.LOG_LEVEL: str = _env("LOG_LEVEL", "DEBUG", str)

        self.ENABLE_TLS: bool = _env("ENABLE_TLS", False, bool)

        self.WATCHER_ENABLED: bool = _env("WATCHER_ENABLED", True, bool)
        self.WATCHER_PERIODIC_SCAN_SECONDS: int = _env(
            "WATCHER_PERIODIC_SCAN_SECONDS", 30, int
        )
        self.FPGKI_FORMAT_ENABLED: bool = _env("FPGKI_FORMAT_ENABLED", False, bool)

    @property
    def APP_NAME(self) -> str:
        return _pyproject_value(self.files.PYPROJECT_FILE_PATH, "name", "hb-store-m1")

    @property
    def APP_VERSION(self) -> str:
        return _pyproject_value(self.files.PYPROJECT_FILE_PATH, "version", "0.0.1")

    @property
    def SERVER_URL(self) -> str:
        scheme = "https" if self.ENABLE_TLS else "http"
        default_port = 443 if self.ENABLE_TLS else 80
        return (
            f"{scheme}://{self.SERVER_IP}"
            if self.SERVER_PORT == default_port
            else f"{scheme}://{self.SERVER_IP}:{self.SERVER_PORT}"
        )


class Globals:
    PATHS = _GlobalPaths()
    FILES = _GlobalFiles(PATHS)
    ENVS = _GlobalEnvs(FILES)
