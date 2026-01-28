import json
from urllib.parse import quote

import settings
from utils.log_utils import log
from utils.pkg_utils import extract_pkg_data


def run(pkgs):
    """Build index.json and index-cache.json from scanned PKGs."""
    def load_cache():
        try:
            if settings.CACHE_PATH.exists():
                return json.loads(settings.CACHE_PATH.read_text())
        except Exception:
            pass
        return {"version": 1, "pkgs": {}}

    def save_cache(cache):
        settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        settings.CACHE_PATH.write_text(json.dumps(cache, indent=2))
        log("created", "Generated: index-cache.json", module="AUTO_INDEXER")

    cache = load_cache()
    apps = []
    new_cache_pkgs = {}

    for pkg, data in pkgs:
        try:
            stat = pkg.stat()
        except Exception:
            continue

        rel = pkg.relative_to(settings.PKG_DIR).as_posix()
        cache_entry = cache["pkgs"].get(rel)
        cache_hit = (
            cache_entry
            and cache_entry.get("size") == stat.st_size
            and cache_entry.get("mtime") == stat.st_mtime
            and isinstance(cache_entry.get("data"), dict)
        )

        if cache_hit:
            data = cache_entry["data"]
        else:
            cache_entry = {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "data": data,
            }

        new_cache_pkgs[rel] = cache_entry

        title = data["title"]
        titleid = data["titleid"]
        version = data["version"]
        base_category = data.get("category")
        apptype = data["apptype"]
        region = data.get("region")

        if settings.APP_DIR in pkg.parents:
            apptype = "app"
            category = "ap"
        else:
            category = base_category

        settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        icon_out = settings.MEDIA_DIR / f"{titleid}.png"
        if not icon_out.exists():
            icon_bytes = extract_pkg_data(pkg, include_icon=True)["icon_bytes"]
            if icon_bytes:
                icon_out.write_bytes(icon_bytes)
                log(
                    "created",
                    f"Extracted: {titleid} PKG icon to {icon_out}",
                    module="AUTO_INDEXER",
                )

        pkg_url = f"{settings.BASE_URL}/pkg/{quote(rel, safe='/')}"
        icon_url = f"{settings.BASE_URL}/_media/{quote(f'{titleid}.png')}"

        app = {
            "id": titleid,
            "name": title,
            "version": version,
            "apptype": apptype,
            "pkg": pkg_url,
            "icon": icon_url
        }
        if category:
            app["category"] = category
        if region:
            app["region"] = region
        apps.append(app)

    cache["pkgs"] = new_cache_pkgs
    save_cache(cache)

    with open(settings.INDEX_PATH, "w") as f:
        json.dump({"apps": apps}, f, indent=2)

    log("created", "Generated: index.json", module="AUTO_INDEXER")
    return 0
