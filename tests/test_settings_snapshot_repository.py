from __future__ import annotations

from pathlib import Path

from homebrew_cdn_m1_server.application.repositories.settings_snapshot_repository import (
    SettingsSnapshotRepository,
)


def test_settings_snapshot_repository_given_hash_when_save_then_load_roundtrip(
    temp_workspace: Path,
) -> None:
    settings_path = temp_workspace / "configs" / "settings.ini"
    snapshot_path = temp_workspace / "data" / "internal" / "catalog" / "settings-snapshot.json"
    _ = settings_path.write_text("SERVER_IP=127.0.0.1\n", encoding="utf-8")
    repository = SettingsSnapshotRepository(snapshot_path, settings_path)

    repository.save("abc123")

    assert repository.load() == "abc123"


def test_settings_snapshot_repository_given_settings_changed_when_current_hash_then_changes(
    temp_workspace: Path,
) -> None:
    settings_path = temp_workspace / "configs" / "settings.ini"
    snapshot_path = temp_workspace / "data" / "internal" / "catalog" / "settings-snapshot.json"
    _ = settings_path.write_text("SERVER_IP=127.0.0.1\n", encoding="utf-8")
    repository = SettingsSnapshotRepository(snapshot_path, settings_path)

    first = repository.current_hash()
    _ = settings_path.write_text("SERVER_IP=10.0.0.20\n", encoding="utf-8")
    second = repository.current_hash()

    assert first != second
