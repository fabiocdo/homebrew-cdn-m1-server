import json
import sqlite3
from urllib.parse import quote

import settings
from utils.log_utils import log
from utils.pkg_utils import extract_pkg_data


def ensure_icon(pkg, data):
    titleid = data.get("titleid")
    if not titleid:
        return False
    settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    icon_out = settings.MEDIA_DIR / f"{titleid}.png"
    if icon_out.exists():
        return False
    icon_bytes = extract_pkg_data(pkg, include_icon=True)["icon_bytes"]
    if icon_bytes:
        icon_out.write_bytes(icon_bytes)
        log("info", f"Extracted icon: {icon_out}", module="AUTO_INDEXER")
        return True
    return False


def update_index_json(pkgs):
    """Update index.json and index-cache.json from scanned PKGs."""
    if settings.INDEX_JSON_ENABLED is False:
        log("info", "INDEX_JSON_ENABLED is false; skipping index generation", module="AUTO_INDEXER")
        return 0, 0
    icon_extracted = 0

    def load_cache():
        try:
            if settings.CACHE_PATH.exists():
                return json.loads(settings.CACHE_PATH.read_text())
        except Exception:
            pass
        return {"version": 1, "pkgs": {}}

    def save_cache(cache):
        settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        new_content = json.dumps(cache, indent=2)
        if settings.CACHE_PATH.exists():
            try:
                if settings.CACHE_PATH.read_text() == new_content:
                    return False
            except Exception:
                pass
        settings.CACHE_PATH.write_text(new_content)
        return True

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

        if ensure_icon(pkg, data):
            icon_extracted += 1

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
    cache_written = save_cache(cache)

    index_payload = {"apps": apps}
    index_written = True
    if settings.INDEX_PATH.exists():
        try:
            if json.loads(settings.INDEX_PATH.read_text()) == index_payload:
                index_written = False
            else:
                settings.INDEX_PATH.write_text(json.dumps(index_payload, indent=2))
        except Exception:
            settings.INDEX_PATH.write_text(json.dumps(index_payload, indent=2))
    else:
        settings.INDEX_PATH.write_text(json.dumps(index_payload, indent=2))

    if cache_written or index_written or icon_extracted:
        message = "Generated index.json and index-cache.json"
        if icon_extracted:
            message = f"{message}; extracted {icon_extracted} icon(s)"
        log("info", message, module="AUTO_INDEXER")
    else:
        log("info", "No indexable changes detected", module="AUTO_INDEXER")
    return cache_written, index_written


def update_store_db(pkgs):
    """Update store.db entries from scanned PKGs."""
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.STORE_DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS homebrews (
                  pid INTEGER,
                  id TEXT,
                  name TEXT,
                  "desc" TEXT,
                  image TEXT,
                  package TEXT,
                  version TEXT,
                  picpath TEXT,
                  desc_1 TEXT,
                  desc_2 TEXT,
                  ReviewStars REAL,
                  Size INTEGER,
                  Author TEXT,
                  apptype TEXT,
                  pv TEXT,
                  main_icon_path TEXT,
                  main_menu_pic TEXT,
                  releaseddate TEXT
                );
                """
            )
            updated = 0
            for pkg, data in pkgs:
                try:
                    stat = pkg.stat()
                except Exception:
                    continue

                title = data.get("title")
                titleid = data.get("titleid")
                version = data.get("version")
                apptype = data.get("apptype")
                if not titleid:
                    continue

                rel = pkg.relative_to(settings.PKG_DIR).as_posix()
                pkg_url = f"{settings.BASE_URL}/pkg/{quote(rel, safe='/')}"
                icon_url = f"{settings.BASE_URL}/_media/{quote(f'{titleid}.png')}"

                conn.execute("DELETE FROM homebrews WHERE id = ?", (titleid,))
                conn.execute(
                    """
                    INSERT INTO homebrews
                    (pid,id,name,"desc",image,package,version,picpath,desc_1,desc_2,ReviewStars,Size,Author,apptype,pv,main_icon_path,main_menu_pic,releaseddate)
                    VALUES
                    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        None,
                        titleid,
                        title,
                        None,
                        icon_url,
                        pkg_url,
                        version,
                        icon_url,
                        None,
                        None,
                        None,
                        stat.st_size,
                        None,
                        apptype,
                        None,
                        icon_url,
                        None,
                        None,
                    ),
                )
                updated += 1
            if updated:
                log("info", f"Updated store.db entries: {updated}", module="AUTO_INDEXER")
    except Exception as exc:
        log("error", f"Failed to update store.db: {exc}", module="AUTO_INDEXER")
    return 0


def run(pkgs):
    """Update store.db and optionally index.json/index-cache.json."""
    update_store_db(pkgs)
    update_index_json(pkgs)
    return 0
