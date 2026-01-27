import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import quote

DATA_DIR = pathlib.Path("/data")
PKG_DIR = DATA_DIR / "pkg"
OUT = DATA_DIR / "index.json"
MEDIA_DIR = DATA_DIR / "_media"
CACHE_DIR = DATA_DIR / "_cache"
DOTNET_GLOBALIZATION_ENV = "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"
APPTYPE_DIRS = ["game", "dlc", "update", "app"]
APP_DIR = PKG_DIR / "app"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
PINK = "\033[1;95m"
RESET = "\033[0m"
CACHE_PATH = CACHE_DIR / "index-cache.json"
PKGTOOL = "/usr/local/bin/pkgtool"
PKG_PASSCODE = None

def parse_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--auto-generate-json-period", required=True, type=float)
    parser.add_argument("--auto-rename-pkgs", required=True)
    parser.add_argument("--auto-rename-template", required=True)
    parser.add_argument(
        "--auto-rename-title-mode",
        required=True,
        choices=["none", "uppercase", "lowercase", "capitalize"],
    )
    return parser.parse_args()

def apply_args(args):
    global BASE_URL
    global AUTO_GENERATE_JSON_PERIOD
    global AUTO_RENAME_PKGS
    global AUTO_RENAME_TEMPLATE
    global AUTO_RENAME_TITLE_MODE

    BASE_URL = args.base_url
    AUTO_GENERATE_JSON_PERIOD = args.auto_generate_json_period
    AUTO_RENAME_PKGS = parse_bool(args.auto_rename_pkgs)
    AUTO_RENAME_TEMPLATE = args.auto_rename_template
    AUTO_RENAME_TITLE_MODE = args.auto_rename_title_mode

def log(action, message):
    if action == "created":
        color = GREEN
        prefix = "[+]"
    elif action == "modified":
        color = YELLOW
        prefix = "[*]"
    elif action == "deleted":
        color = RED
        prefix = "[-]"
    elif action == "error":
        color = PINK
        prefix = "[!]"
    elif action == "info":
        color = RESET
        prefix = "[·]"
    else:
        color = RESET
        prefix = "[*]"
    print(f"{color}{prefix} {message}{RESET}")

def run_pkgtool(args):
    env = os.environ.copy()
    env.setdefault(DOTNET_GLOBALIZATION_ENV, "1")
    result = subprocess.run(
        [PKGTOOL] + args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        )
    return result.stdout


def list_pkg_entries(pkg_path):
    entries = {}
    output = run_pkgtool(["pkg_listentries", str(pkg_path)])
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Offset"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        index = parts[3]
        name = parts[5] if len(parts) >= 6 else parts[4]
        entries[name] = index
    return entries


def parse_sfo_entries(sfo_path):
    entries = {}
    output = run_pkgtool(["sfo_listentries", str(sfo_path)])
    for line in output.splitlines():
        if " = " not in line or " : " not in line:
            continue
        left, value = line.split(" = ", 1)
        name = left.split(" : ", 1)[0].strip()
        entries[name] = value.strip()
    return entries


def parse_sfo_int(value):
    if isinstance(value, int):
        return value
    if not value:
        return None
    if value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            return None
    try:
        return int(value)
    except ValueError:
        return None


def map_apptype(category, app_type):
    if category:
        cat = category.lower()
        category_map = {
            "gd": "game",
            "gp": "update",
            "ac": "dlc",
            "ad": "app",
            "al": "app",
            "ap": "app",
            "bd": "app",
            "dd": "app",
        }
        if cat in category_map:
            return category_map[cat]
    if app_type == 1:
        return "app"
    if app_type == 2:
        return "game"
    return "app"


def region_from_content_id(content_id):
    if not content_id or len(content_id) < 2:
        return None
    prefix = content_id[:2].upper()
    region_map = {
        "UP": "USA",
        "EP": "EUR",
        "JP": "JPN",
        "KP": "KOR",
        "HP": "HKG",
        "TP": "TWN",
        "CP": "CHN",
    }
    return region_map.get(prefix, prefix)


def load_cache():
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text())
    except Exception:
        pass
    return {"version": 1, "pkgs": {}}


def save_cache(cache):
    log("info", "Generating index-cache.json...")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    log("created", "Generated: index-cache.json")


def build_data(info, pkg_path):
    title = info.get("TITLE", pkg_path.stem)
    titleid = info.get("TITLE_ID", pkg_path.stem)
    version = info.get("VERSION", "1.00")
    category = info.get("CATEGORY")
    content_id = info.get("CONTENT_ID")
    app_type = parse_sfo_int(info.get("APP_TYPE"))
    apptype = map_apptype(category, app_type)
    region = region_from_content_id(content_id)

    return {
        "title": title,
        "titleid": titleid,
        "version": version,
        "category": category,
        "content_id": content_id,
        "app_type": app_type,
        "apptype": apptype,
        "region": region,
    }


def sanitize_filename(value):
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-![]().'")
    cleaned = []
    for ch in value:
        if ch.isalnum() or ch in allowed:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    safe = "".join(cleaned)
    safe = safe.replace("/", "_").replace("\\", "_").replace("-", "_").replace(":", "_").strip()
    safe = "_".join(part for part in safe.split() if part)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe


def format_title(value):
    return " ".join(part.capitalize() for part in value.split())


def render_rename(template, data):
    safe = {}
    for key, value in data.items():
        if value is None:
            safe[key] = ""
        elif key == "title":
            title_value = str(value)
            if AUTO_RENAME_TITLE_MODE == "uppercase":
                title_value = title_value.upper()
            elif AUTO_RENAME_TITLE_MODE == "lowercase":
                title_value = title_value.lower()
            elif AUTO_RENAME_TITLE_MODE == "capitalize":
                title_value = format_title(title_value)
            title_value = re.sub(r"([A-Za-z])([0-9])", r"\1_\2", title_value)
            safe[key] = sanitize_filename(title_value)
        else:
            safe[key] = sanitize_filename(str(value))
    try:
        name = template.format_map(safe).strip()
    except ValueError as exc:
        log("error", f"Invalid AUTO_RENAME_TEMPLATE: {exc}. Using fallback.")
        name = "{title} [{titleid}][{apptype}]".format_map(safe).strip()
    if not name.lower().endswith(".pkg"):
        name = f"{name}.pkg"
    return name


def maybe_rename_pkg(pkg_path, title, titleid, apptype, region, version, category, content_id, app_type):
    if not AUTO_RENAME_PKGS:
        return pkg_path
    if not titleid:
        return pkg_path
    new_name = render_rename(
        AUTO_RENAME_TEMPLATE,
        {
            "title": title,
            "titleid": titleid,
            "version": version or "1.00",
            "category": category or "",
            "content_id": content_id or "",
            "app_type": app_type or "",
            "apptype": apptype or "app",
            "region": region or "UNK",
        },
    )
    if pkg_path.name == new_name:
        return pkg_path
    target_path = pkg_path.with_name(new_name)
    if target_path.exists():
        return pkg_path
    try:
        pkg_path.rename(target_path)
        log("modified", f"Renamed PKG to {target_path}")
        return target_path
    except Exception:
        return pkg_path


def build_target_path(pkg_path, apptype, title, titleid, region, version, category, content_id, app_type):
    target_dir = pkg_path.parent
    if apptype in APPTYPE_DIRS and apptype != "app" and APP_DIR not in pkg_path.parents:
        target_dir = PKG_DIR / apptype
    target_name = pkg_path.name
    if AUTO_RENAME_PKGS and titleid:
        target_name = render_rename(
            AUTO_RENAME_TEMPLATE,
            {
                "title": title,
                "titleid": titleid,
                "version": version or "1.00",
                "category": category or "",
                "content_id": content_id or "",
                "app_type": app_type or "",
                "apptype": apptype or "app",
                "region": region or "UNK",
            },
        )
    return target_dir / target_name


def ensure_pkg_location(pkg_path, apptype):
    if apptype not in APPTYPE_DIRS:
        return pkg_path
    if apptype == "app":
        return pkg_path
    if APP_DIR in pkg_path.parents:
        return pkg_path
    target_type = apptype
    target_dir = PKG_DIR / target_type
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / pkg_path.name

    if pkg_path.resolve() == target_path.resolve():
        return pkg_path

    if target_path.exists():
        log("error", f"Target already exists, skipping move: {target_path}")
        return pkg_path

    try:
        shutil.move(str(pkg_path), str(target_path))
    except Exception as e:
        log("error", f"Error moving PKG to {target_path}: {e}")
        return pkg_path

    return target_path


def extract_pkg_entry(pkg_path, entry_id, out_path):
    args = []
    if PKG_PASSCODE:
        args += ["--passcode", PKG_PASSCODE]
    args += ["pkg_extractentry", str(pkg_path), str(entry_id), str(out_path)]
    run_pkgtool(args)


def read_pkg_info(pkg_path):
    try:
        with tempfile.TemporaryDirectory(prefix="pkg_extract_") as tmpdir:
            entries = list_pkg_entries(pkg_path)
            sfo_entry = None
            icon_entry = None
            for name, entry_id in entries.items():
                lower = name.lower()
                normalized = lower.replace(".", "_")
                if "param_sfo" in normalized:
                    sfo_entry = entry_id
                elif normalized in {"icon0_png", "icon0_00_png", "pic0_png"}:
                    if icon_entry is None or normalized == "icon0_png":
                        icon_entry = entry_id

            if sfo_entry is None:
                log("error", f"PARAM_SFO not found in {pkg_path}")
                return {}, None

            tmp_root = pathlib.Path(tmpdir)
            sfo_path = tmp_root / "param.sfo"
            extract_pkg_entry(pkg_path, sfo_entry, sfo_path)
            info = parse_sfo_entries(sfo_path)

            return info, icon_entry
    except Exception:
        return {}, None


def read_icon_bytes(pkg_path, icon_entry):
    try:
        with tempfile.TemporaryDirectory(prefix="pkg_extract_") as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            icon_path = tmp_root / "icon0.png"
            extract_pkg_entry(pkg_path, icon_entry, icon_path)
            if icon_path.exists():
                return icon_path.read_bytes()
    except Exception:
        return None

def ensure_base_dirs():
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def init_layout():
    for apptype_dir in APPTYPE_DIRS:
        apptype_path = PKG_DIR / apptype_dir
        if not apptype_path.exists():
            apptype_path.mkdir(parents=True, exist_ok=True)
            log("created", f"Created PKG directory {apptype_path}")
    if not APP_DIR.exists():
        APP_DIR.mkdir(parents=True, exist_ok=True)
        log("created", f"Created PKG directory {APP_DIR}")

    marker_path = PKG_DIR / "_PUT_YOUR_PKGS_HERE"
    if not marker_path.exists():
        marker_path.write_text("Place PKG files in this directory or its subfolders.\n")
        log("created", f"Created marker file {marker_path}")

def build_index(move_only):
    cache = load_cache()
    new_cache_pkgs = {}
    duplicate_found = False
    apps = []

    for pkg in PKG_DIR.rglob("*.pkg"):
        if any(part.startswith("_") for part in pkg.parts):
            continue
        rel_pre = pkg.relative_to(PKG_DIR).as_posix()
        try:
            stat = pkg.stat()
        except Exception:
            continue

        cache_entry = cache["pkgs"].get(rel_pre)
        cache_hit = (
            cache_entry
            and cache_entry.get("size") == stat.st_size
            and cache_entry.get("mtime") == stat.st_mtime
            and isinstance(cache_entry.get("data"), dict)
        )

        if cache_hit:
            data = cache_entry["data"]
            icon_entry = cache_entry.get("icon_entry")
        else:
            info, icon_entry = read_pkg_info(pkg)
            data = build_data(info, pkg)
            cache_entry = {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "data": data,
                "icon_entry": icon_entry,
            }

        title = data["title"]
        titleid = data["titleid"]
        version = data["version"]
        base_category = data.get("category")
        apptype = data["apptype"]
        region = data.get("region")

        target_path = build_target_path(
            pkg,
            apptype,
            title,
            titleid,
            region,
            version,
            base_category,
            data.get("content_id"),
            data.get("app_type"),
        )
        if target_path.exists() and target_path.resolve() != pkg.resolve():
            log("error", f"Duplicate target exists, skipping: {target_path}")
            duplicate_found = True
            continue
        if target_path.resolve() != pkg.resolve():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(pkg), str(target_path))
                if target_path.name != pkg.name:
                    log("modified", f"Renamed PKG to {target_path}")
                pkg = target_path
            except Exception as e:
                log("error", f"Error moving PKG to {target_path}: {e}")
                continue
        rel = pkg.relative_to(PKG_DIR).as_posix()
        new_cache_pkgs[rel] = cache_entry

        if move_only:
            continue

        if APP_DIR in pkg.parents:
            apptype = "app"
            category = "ap"
        else:
            category = base_category

        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        icon_out = MEDIA_DIR / f"{titleid}.png"
        if icon_entry is not None and not icon_out.exists():
            icon_bytes = read_icon_bytes(pkg, icon_entry)
            if icon_bytes:
                icon_out.write_bytes(icon_bytes)
                log("created", f"Extracted: {titleid} PKG icon to {icon_out}")

        pkg_rel = pkg.relative_to(PKG_DIR).as_posix()
        pkg_url = f"{BASE_URL}/pkg/{quote(pkg_rel, safe='/')}"
        icon_url = f"{BASE_URL}/_media/{quote(f'{titleid}.png')}"

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

    if move_only:
        cache["pkgs"] = new_cache_pkgs
        if duplicate_found:
            return 2
        return 0

    if duplicate_found:
        return 0

    cache["pkgs"] = new_cache_pkgs
    save_cache(cache)

    with open(OUT, "w") as f:
        json.dump({"apps": apps}, f, indent=2)

    log("created", "Generated: index.json")
    return 0

def watch_pkg_dir():
    if not PKG_DIR.exists():
        return

    last_moved_from = ""
    debounce_timer = None

    def schedule_generate():
        nonlocal debounce_timer
        if debounce_timer and debounce_timer.is_alive():
            debounce_timer.cancel()

        def run():
            nonlocal debounce_timer
            debounce_timer = None
            build_index(False)

        debounce_timer = threading.Timer(AUTO_GENERATE_JSON_PERIOD, run)
        debounce_timer.daemon = True
        debounce_timer.start()

    cmd = [
        "inotifywait",
        "-m",
        "-r",
        "-e",
        "create",
        "-e",
        "delete",
        "-e",
        "move",
        "-e",
        "close_write",
        "--format",
        "%w%f|%e",
        str(PKG_DIR),
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if process.stdout is None:
        return

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            log("info", line)
            continue
        path, events = line.split("|", 1)
        if "MOVED_FROM" in events:
            last_moved_from = path
            continue
        if "MOVED_TO" in events:
            if last_moved_from:
                log("modified", f"Moved: {last_moved_from} -> {path}")
                last_moved_from = ""
            else:
                log("modified", f"Moved: {path}")
            if build_index(True) == 0:
                schedule_generate()
            continue
        if "CREATE" in events or "DELETE" in events:
            if "DELETE" in events:
                log("deleted", f"Change detected: {events} {path}")
            else:
                log("created", f"Change detected: {events} {path}")
            if build_index(True) == 0:
                schedule_generate()
            continue
        log("modified", f"Change detected: {events} {path}")
        if build_index(True) == 0:
            schedule_generate()

def main():
    apply_args(parse_args())
    ensure_base_dirs()
    init_layout()
    build_index(False)
    watch_pkg_dir()
    return 0

if __name__ == "__main__":
    sys.exit(main())
