import hashlib
import json

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
            LogUtils.log_error(f"Failed to read STORE CACHE: {e}")
            return Output(Status.ERROR, {})

        return Output(Status.OK, data)

    @staticmethod
    def write_store_db_cache(db: StoreDB) -> Output:
        cache: dict[str, str] = {}

        for row in db:
            data = row.row
            key = data[StoreDB.Column.CONTENT_ID]
            values = [data[field] for field in StoreDB.Column]
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
        return Output(Status.OK, cache)


CacheUtils = CacheUtils()
