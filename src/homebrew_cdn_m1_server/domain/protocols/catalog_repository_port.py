from __future__ import annotations

from typing import Protocol

from homebrew_cdn_m1_server.domain.entities.catalog_item import CatalogItem


class CatalogRepositoryPort(Protocol):
    def init_schema(self, schema_sql: str) -> None: ...

    def upsert(self, item: CatalogItem) -> None: ...

    def list_items(self) -> list[CatalogItem]: ...

    def delete_by_pkg_paths_not_in(self, existing_pkg_paths: set[str]) -> int: ...
