from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import final


@final
class SettingsSnapshotRepository:
    def __init__(self, snapshot_path: Path, settings_path: Path) -> None:
        self._snapshot_path = snapshot_path
        self._settings_path = settings_path

    def current_hash(self) -> str:
        try:
            raw = self._settings_path.read_bytes()
        except OSError:
            raw = b""
        return hashlib.blake2b(raw, digest_size=16).hexdigest()

    def load(self) -> str:
        if not self._snapshot_path.exists():
            return ""
        try:
            raw_obj = json.loads(self._snapshot_path.read_text("utf-8"))
        except (OSError, ValueError, TypeError):
            return ""

        if not isinstance(raw_obj, dict):
            return ""
        value = raw_obj.get("hash")
        if not isinstance(value, str):
            return ""
        normalized = value.strip()
        return normalized

    def save(self, hash_value: str) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"hash": str(hash_value or "").strip()}
        _ = self._snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
