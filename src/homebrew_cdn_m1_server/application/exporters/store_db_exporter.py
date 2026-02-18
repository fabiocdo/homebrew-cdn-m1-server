from __future__ import annotations

from collections.abc import Sequence
import sqlite3
from pathlib import Path
from typing import final, override

from homebrew_cdn_m1_server.domain.protocols.output_exporter_protocol import OutputExporterProtocol
from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget
from homebrew_cdn_m1_server.domain.models.catalog_item import CatalogItem


@final
class StoreDbExporter(OutputExporterProtocol):
    target: OutputTarget = OutputTarget.HB_STORE
    _BYTES_PER_MB: int = 1024 * 1024
    _BYTES_PER_GB: int = 1024 * 1024 * 1024

    def __init__(self, output_db_path: Path, init_sql_path: Path, base_url: str) -> None:
        self._output_db_path = output_db_path
        self._init_sql_path = init_sql_path
        self._base_url = base_url.rstrip("/")

    def _canonical_pkg_url(self, item: CatalogItem) -> str:
        return f"{self._base_url}/pkg/{item.app_type.value}/{item.content_id.value}.pkg"

    def _download_url(self, item: CatalogItem) -> str:
        return (
            f"{self._base_url}/download.php?"
            f"tid={item.title_id}&cid={item.content_id.value}&ver={item.version}"
        )

    def _canonical_media_url(self, item: CatalogItem, suffix: str) -> str:
        return f"{self._base_url}/pkg/media/{item.content_id.value}_{suffix}.png"

    @classmethod
    def _format_store_size(cls, size_bytes: int) -> str:
        normalized = max(0, int(size_bytes))
        if normalized >= cls._BYTES_PER_GB:
            return f"{normalized / cls._BYTES_PER_GB:.2f} GB"
        if normalized >= cls._BYTES_PER_MB:
            return f"{normalized / cls._BYTES_PER_MB:.2f} MB"
        return f"{normalized} B"

    def _row(self, item: CatalogItem) -> tuple[object, ...]:
        row = {
            "content_id": item.content_id.value,
            "id": item.title_id,
            "name": item.title,
            "desc": None,
            "image": self._canonical_media_url(item, "icon0"),
            "package": self._download_url(item),
            "version": item.version,
            "picpath": f"/user/app/NPXS39041/storedata/{item.content_id.value}.png",
            "desc_1": None,
            "desc_2": None,
            "ReviewStars": None,
            "Size": self._format_store_size(item.pkg_size),
            "Author": None,
            "apptype": item.app_type.store_db_label,
            "pv": None,
            "main_icon_path": self._canonical_media_url(item, "pic0") if item.pic0_path else None,
            "main_menu_pic": self._canonical_media_url(item, "pic1") if item.pic1_path else None,
            "releaseddate": item.release_date or "1970-01-01",
            "number_of_downloads": int(item.downloads),
            "github": None,
            "video": None,
            "twitter": None,
            "md5": None,
        }
        return (
            row["content_id"],
            row["id"],
            row["name"],
            row["desc"],
            row["image"],
            row["package"],
            row["version"],
            row["picpath"],
            row["desc_1"],
            row["desc_2"],
            row["ReviewStars"],
            row["Size"],
            row["Author"],
            row["apptype"],
            row["pv"],
            row["main_icon_path"],
            row["main_menu_pic"],
            row["releaseddate"],
            row["number_of_downloads"],
            row["github"],
            row["video"],
            row["twitter"],
            row["md5"],
        )

    @override
    def export(self, items: Sequence[CatalogItem]) -> list[Path]:
        self._output_db_path.parent.mkdir(parents=True, exist_ok=True)
        init_sql = self._init_sql_path.read_text("utf-8")

        tmp_db = self._output_db_path.with_suffix(self._output_db_path.suffix + ".tmp")
        if tmp_db.exists():
            _ = tmp_db.unlink()

        conn = sqlite3.connect(str(tmp_db))
        try:
            _ = conn.executescript(init_sql)
            rows = [self._row(item) for item in items]
            if rows:
                _ = conn.executemany(
                    """
                    INSERT INTO homebrews (
                        content_id, id, name, desc, image, package, version,
                        picpath, desc_1, desc_2, ReviewStars, Size, Author,
                        apptype, pv, main_icon_path, main_menu_pic, releaseddate,
                        number_of_downloads, github, video, twitter, md5
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            conn.commit()
        finally:
            conn.close()

        _ = tmp_db.replace(self._output_db_path)
        return [self._output_db_path]

    @override
    def cleanup(self) -> list[Path]:
        if not self._output_db_path.exists():
            return []
        _ = self._output_db_path.unlink()
        return [self._output_db_path]
