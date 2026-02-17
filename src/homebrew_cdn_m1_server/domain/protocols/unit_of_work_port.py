from __future__ import annotations

from typing import Protocol

from homebrew_cdn_m1_server.domain.protocols.catalog_repository_port import CatalogRepositoryPort


class UnitOfWorkPort(Protocol):
    catalog: CatalogRepositoryPort

    def __enter__(self) -> "UnitOfWorkPort": ...

    def __exit__(self, exc_type, exc, tb) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
