from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import final

from homebrew_cdn_m1_server.application.repositories.sqlite_catalog_repository import (
    SqliteCatalogRepository,
)


@final
class SqliteUnitOfWork:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self.catalog: SqliteCatalogRepository

    def __enter__(self) -> "SqliteUnitOfWork":
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        _ = self._conn.execute("PRAGMA journal_mode=WAL")
        _ = self._conn.execute("PRAGMA foreign_keys=ON")
        self.catalog = SqliteCatalogRepository(self._conn, self._db_path)
        _ = self._conn.execute("BEGIN")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._conn is None:
            return
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self._conn.close()
        self._conn = None

    def commit(self) -> None:
        if self._conn is not None:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn is not None:
            self._conn.rollback()
