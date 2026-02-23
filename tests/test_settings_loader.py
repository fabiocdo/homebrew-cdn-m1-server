from __future__ import annotations

from pathlib import Path

from homebrew_cdn_m1_server.config.settings_loader import SettingsLoader
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget


def test_settings_loader_given_settings_ini_when_load_then_parses_expected_fields(
    temp_workspace: Path,
):
    settings = temp_workspace / "configs" / "settings.ini"
    _ = settings.write_text(
        "\n".join(
            [
                "SERVER_IP=127.0.0.5",
                "SERVER_PORT=8080",
                "ENABLE_TLS=true",
                "LOG_LEVEL=warn",
                "RECONCILE_PKG_PREPROCESS_WORKERS=4",
                "RECONCILE_CRON_EXPRESSION=*/2 * * * *",
                "EXPORT_TARGETS=hb-store,fpkgi,invalid",
                "PKGTOOL_TIMEOUT_SECONDS=900",
            ]
        ),
        encoding="utf-8",
    )

    config = SettingsLoader.load(settings)

    assert config.user.server_ip == "127.0.0.5"
    assert config.user.server_port == 8080
    assert config.user.enable_tls is True
    assert config.user.log_level == "warning"
    assert config.user.reconcile_pkg_preprocess_workers == 4
    assert config.user.reconcile_cron_expression == "*/2 * * * *"
    assert config.user.output_targets == (OutputTarget.HB_STORE, OutputTarget.FPKGI)
    assert config.user.pkgtool_timeout_seconds == 900
    assert str(config.paths.catalog_db_path).endswith("data/internal/catalog/catalog.db")
    assert str(config.paths.snapshot_path).endswith("data/internal/catalog/pkgs-snapshot.json")
    assert str(config.paths.settings_snapshot_path).endswith(
        "data/internal/catalog/settings-snapshot.json"
    )
    assert str(config.paths.store_db_path).endswith("data/share/hb-store/store.db")
    assert str(config.paths.fpkgi_share_dir).endswith("data/share/fpkgi")
    assert str(config.paths.media_dir).endswith("data/share/pkg/media")


def test_settings_loader_given_tls_enabled_and_empty_port_then_uses_host_without_port(
    temp_workspace: Path,
):
    settings = temp_workspace / "configs" / "settings.ini"
    _ = settings.write_text(
        "\n".join(
            [
                "SERVER_IP=127.0.0.5",
                "SERVER_PORT=",
                "ENABLE_TLS=true",
            ]
        ),
        encoding="utf-8",
    )

    config = SettingsLoader.load(settings)

    assert config.user.server_port is None
    assert config.base_url == "https://127.0.0.5"


def test_settings_loader_given_tls_disabled_and_empty_port_then_uses_host_without_port(
    temp_workspace: Path,
):
    settings = temp_workspace / "configs" / "settings.ini"
    _ = settings.write_text(
        "\n".join(
            [
                "SERVER_IP=127.0.0.5",
                "SERVER_PORT=",
                "ENABLE_TLS=false",
            ]
        ),
        encoding="utf-8",
    )

    config = SettingsLoader.load(settings)

    assert config.user.server_port is None
    assert config.base_url == "http://127.0.0.5"


def test_settings_loader_given_blank_values_when_load_then_maps_them_to_none(
    temp_workspace: Path,
):
    settings = temp_workspace / "configs" / "settings.ini"
    _ = settings.write_text(
        "\n".join(
            [
                "SERVER_IP=",
                "SERVER_PORT=",
                "ENABLE_TLS=",
                "LOG_LEVEL=",
                "RECONCILE_PKG_PREPROCESS_WORKERS=",
                "RECONCILE_CRON_EXPRESSION=",
                "EXPORT_TARGETS=",
                "PKGTOOL_TIMEOUT_SECONDS=",
            ]
        ),
        encoding="utf-8",
    )

    config = SettingsLoader.load(settings)

    assert config.user.server_ip is None
    assert config.user.server_port is None
    assert config.user.enable_tls is None
    assert config.user.log_level is None
    assert config.user.reconcile_pkg_preprocess_workers is None
    assert config.user.reconcile_cron_expression is None
    assert config.user.output_targets is None
    assert config.user.pkgtool_timeout_seconds is None
