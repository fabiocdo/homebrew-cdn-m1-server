from __future__ import annotations

from typing import ClassVar
from typing import cast

from pydantic import BaseModel, ConfigDict, Field


class FpkgiItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    title_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    release: str
    size: str = Field(min_length=1)
    min_fw: str
    cover_url: str = Field(min_length=1)


class FpkgiDocument(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    DATA: dict[str, FpkgiItem] = Field(default_factory=dict)


def build_fpkgi_schema() -> dict[str, object]:
    return cast(dict[str, object], FpkgiDocument.model_json_schema())
