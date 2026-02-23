from __future__ import annotations

from pathlib import Path
from typing import ClassVar, final

from homebrew_cdn_m1_server.config.settings_models import UserSettings
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.app_config import AppConfig, RuntimePaths


@final
class SettingsLoader:
    _KEY_MAP: ClassVar[dict[str, str]] = {
        "SERVER_IP": "server_ip",
        "SERVER_PORT": "server_port",
        "ENABLE_TLS": "enable_tls",
        "LOG_LEVEL": "log_level",
        "RECONCILE_PKG_PREPROCESS_WORKERS": "reconcile_pkg_preprocess_workers",
        "RECONCILE_CRON_EXPRESSION": "reconcile_cron_expression",
        "EXPORT_TARGETS": "output_targets",
        "PKGTOOL_TIMEOUT_SECONDS": "pkgtool_timeout_seconds",
    }

    @staticmethod
    def _parse_key_value_file(path: Path) -> dict[str, str]:
        data: dict[str, str] = {}
        if not path.exists():
            return data

        for raw_line in path.read_text("utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
        return data

    @staticmethod
    def _parse_bool(value: str) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _to_user_settings(cls, raw: dict[str, str]) -> UserSettings:
        mapped: dict[str, object] = {}
        for key, value in raw.items():
            target = cls._KEY_MAP.get(key)
            if not target:
                continue
            text = str(value or "").strip()
            if not text:
                mapped[target] = None
                continue
            if target in {
                "server_port",
                "reconcile_pkg_preprocess_workers",
                "pkgtool_timeout_seconds",
            }:
                try:
                    mapped[target] = int(text)
                except ValueError:
                    mapped[target] = None
                continue
            if target == "enable_tls":
                mapped[target] = cls._parse_bool(value)
                continue
            if target == "output_targets":
                parsed_targets: list[OutputTarget] = []
                for item in text.split(","):
                    normalized = item.strip().lower()
                    if not normalized:
                        continue
                    try:
                        parsed_targets.append(OutputTarget(normalized))
                    except ValueError:
                        continue
                seen: set[OutputTarget] = set()
                deduped: list[OutputTarget] = []
                for parsed in parsed_targets:
                    if parsed in seen:
                        continue
                    seen.add(parsed)
                    deduped.append(parsed)
                mapped[target] = tuple(deduped) if deduped else None
                continue

            mapped[target] = text

        return UserSettings.model_validate(mapped)

    @staticmethod
    def _build_paths(app_root: Path, settings_path: Path) -> RuntimePaths:
        data_dir = app_root / "data"
        internal_dir = data_dir / "internal"
        share_dir = data_dir / "share"
        hb_store_share_dir = share_dir / "hb-store"
        fpkgi_share_dir = share_dir / "fpkgi"
        catalog_dir = internal_dir / "catalog"
        pkg_root = share_dir / "pkg"
        return RuntimePaths(
            app_root=app_root,
            init_dir=app_root / "init",
            data_dir=data_dir,
            internal_dir=internal_dir,
            share_dir=share_dir,
            hb_store_share_dir=hb_store_share_dir,
            fpkgi_share_dir=fpkgi_share_dir,
            catalog_dir=catalog_dir,
            cache_dir=catalog_dir,
            logs_dir=internal_dir / "logs",
            errors_dir=internal_dir / "errors",
            hb_store_update_dir=hb_store_share_dir / "update",
            public_index_path=share_dir / "index.html",
            pkg_root=pkg_root,
            media_dir=pkg_root / "media",
            app_dir=pkg_root / "app",
            game_dir=pkg_root / "game",
            dlc_dir=pkg_root / "dlc",
            pkg_update_dir=pkg_root / "update",
            save_dir=pkg_root / "save",
            unknown_dir=pkg_root / "unknown",
            catalog_db_path=catalog_dir / "catalog.db",
            store_db_path=hb_store_share_dir / "store.db",
            snapshot_path=catalog_dir / "pkgs-snapshot.json",
            settings_snapshot_path=catalog_dir / "settings-snapshot.json",
            settings_path=settings_path,
            pkgtool_bin_path=app_root / "bin" / "pkgtool",
        )

    @classmethod
    def load(cls, settings_path: Path | None = None) -> AppConfig:
        app_root = Path.cwd()
        resolved_settings = settings_path or app_root / "configs" / "settings.ini"
        raw = cls._parse_key_value_file(resolved_settings)
        user = cls._to_user_settings(raw)
        paths = cls._build_paths(app_root, resolved_settings)
        return AppConfig(user=user, paths=paths)
