from __future__ import annotations

from typing import Annotated
from typing import ClassVar
from typing import cast

from pydantic import ConfigDict, Field, RootModel


SnapshotMeta = Annotated[list[int], Field(min_length=2, max_length=2)]


class SnapshotDocument(RootModel[dict[str, SnapshotMeta]]):
    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True)


def build_snapshot_schema() -> dict[str, object]:
    return cast(dict[str, object], SnapshotDocument.model_json_schema())
