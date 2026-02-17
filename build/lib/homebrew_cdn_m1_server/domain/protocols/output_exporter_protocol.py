from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem


class OutputExporterProtocol(Protocol):
    target: OutputTarget

    def export(self, items: Sequence[CatalogItem]) -> list[Path]: ...

    def cleanup(self) -> list[Path]: ...
