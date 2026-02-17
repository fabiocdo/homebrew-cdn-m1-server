from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homebrew_cdn_m1_server.config.settings_models import UserSettings


@dataclass(frozen=True)
class RuntimePaths:
    app_root: Path
    init_dir: Path
    data_dir: Path
    internal_dir: Path
    share_dir: Path
    hb_store_share_dir: Path
    fpkgi_share_dir: Path
    catalog_dir: Path
    cache_dir: Path
    logs_dir: Path
    errors_dir: Path
    hb_store_update_dir: Path
    public_index_path: Path
    pkg_root: Path
    media_dir: Path
    app_dir: Path
    game_dir: Path
    dlc_dir: Path
    pkg_update_dir: Path
    save_dir: Path
    unknown_dir: Path
    catalog_db_path: Path
    store_db_path: Path
    snapshot_path: Path
    settings_path: Path
    pkgtool_bin_path: Path


@dataclass(frozen=True)
class AppConfig:
    user: UserSettings
    paths: RuntimePaths
    reconcile_interval_seconds: int = 30
    reconcile_file_stable_seconds: int = 15

    @property
    def base_url(self) -> str:
        scheme = "https" if self.user.enable_tls else "http"
        default_port = 443 if self.user.enable_tls else 80
        if self.user.server_port == default_port:
            return f"{scheme}://{self.user.server_ip}"
        return f"{scheme}://{self.user.server_ip}:{self.user.server_port}"
