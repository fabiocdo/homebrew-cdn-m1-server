import hashlib
import json
from typing import Iterable, Mapping, Any

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.storedb import StoreDB
from hb_store_m1.utils.log_utils import LogUtils


class CacheUtils:

    @staticmethod
    def read_store_db_cache() -> Output:

        path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH

        if not path.exists():
            LogUtils.log_debug(f"Skipping {path.name.upper()} read. File not found")
            return Output(Status.NOT_FOUND, {})

        try:
            data = json.loads(path.read_text("utf-8"))

        except (json.JSONDecodeError, OSError) as e:

            LogUtils.error(f"Failed to read STORE CACHE: {e}")
            return Output(Status.ERROR, {})

        return data

    @staticmethod
    def write_store_db_cache(rows: Iterable[Any] | Mapping[str, Any]) -> dict[str, str]:

        def get_value(row: Any, field: str) -> Any:
            if isinstance(row, Mapping):
                return row.get(field)

            return getattr(row, field, None)

        def normalize(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, (str, int, float, bool)):
                return value
            return str(value)

        iterable = rows.values() if isinstance(rows, Mapping) else rows
        cache: dict[str, str] = {}
        fields = [col.value for col in StoreDB.Columns]
        for row in iterable or []:
            key = normalize(get_value(row, "content_id"))
            if not key:
                continue
            values = [normalize(get_value(row, field)) for field in fields]
            payload = json.dumps(
                values, ensure_ascii=True, separators=(",", ":")
            ).encode("utf-8")
            cache[str(key)] = hashlib.md5(payload).hexdigest()

        path = Globals.FILES.STORE_CACHE_JSON_FILE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cache, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return cache


CacheUtils = CacheUtils()
