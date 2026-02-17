from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import cast, final

from pydantic import ValidationError

from homebrew_cdn_m1_server.application.repositories.snapshot_contract import (
    SnapshotDocument,
    build_snapshot_schema,
)


@final
class JsonSnapshotRepository:
    def __init__(self, snapshot_path: Path, schema_path: Path) -> None:
        self._snapshot_path = snapshot_path
        self._schema_path = schema_path
        self._validate_schema_contract()

    def _validate_schema_contract(self) -> None:
        if not self._schema_path.exists():
            raise FileNotFoundError(f"Snapshot schema not found: {self._schema_path}")

        raw = self._schema_path.read_text("utf-8")
        actual = cast(object, json.loads(raw))
        if not isinstance(actual, dict):
            raise ValueError(f"Snapshot schema must be a JSON object: {self._schema_path}")

        expected = build_snapshot_schema()
        if actual != expected:
            raise ValueError(
                f"Snapshot schema file is out of sync with repository contract: {self._schema_path}"
            )

    def load(self) -> Mapping[str, tuple[int, int]]:
        if not self._snapshot_path.exists():
            return {}
        try:
            raw_obj = cast(object, json.loads(self._snapshot_path.read_text("utf-8")))
            document = SnapshotDocument.model_validate(raw_obj)
        except (OSError, ValueError, TypeError, ValidationError):
            return {}
        return {str(path): (int(meta[0]), int(meta[1])) for path, meta in document.root.items()}

    def save(self, snapshot: Mapping[str, tuple[int, int]]) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = {
            str(path): [int(meta[0]), int(meta[1])] for path, meta in snapshot.items()
        }
        document = SnapshotDocument.model_validate(normalized)
        data = cast(dict[str, object], document.model_dump(mode="json"))
        _ = self._snapshot_path.write_text(
            json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
