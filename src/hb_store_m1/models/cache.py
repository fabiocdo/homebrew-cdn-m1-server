from enum import StrEnum

from pydantic import BaseModel, Field, TypeAdapter


class CacheMeta(BaseModel):
    count: int = 0
    total_size: int = 0
    latest_mtime: int = 0


class CacheSection(BaseModel):
    meta: CacheMeta = Field(default_factory=CacheMeta)
    content: dict[str, str] = Field(default_factory=dict)


CACHE_ADAPTER = TypeAdapter(dict[str, CacheSection])


class Cache:
    class Key(StrEnum):
        META = "meta"
        CONTENT = "content"
        COUNT = "count"
        TOTAL_SIZE = "total_size"
        LATEST_MTIME = "latest_mtime"
