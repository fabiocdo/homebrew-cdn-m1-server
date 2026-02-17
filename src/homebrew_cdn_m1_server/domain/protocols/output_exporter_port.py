from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from homebrew_cdn_m1_server.config.settings_models import OutputTarget
from homebrew_cdn_m1_server.domain.entities.catalog_item import CatalogItem


class OutputExporterPort(Protocol):
    target: OutputTarget

    def export(self, items: Sequence[CatalogItem]) -> list[Path]: ...

    def cleanup(self) -> list[Path]: ...
