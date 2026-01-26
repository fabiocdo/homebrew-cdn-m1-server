import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from urllib.parse import quote

BASE_URL = os.environ.get("BASE_URL", "http://YOUR_IP:8080")
DATA_DIR = pathlib.Path("/data")
PKG_DIR = DATA_DIR / "pkg"
OUT = DATA_DIR / "index.json"
MEDIA_DIR = DATA_DIR / "_media"
ICONS_DIR = MEDIA_DIR / "icons"
PKGTOOL = os.environ.get("PKGTOOL", "/usr/local/bin/pkgtool")
PKG_PASSCODE = os.environ.get("PKG_PASSCODE")
DOTNET_GLOBALIZATION_ENV = "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"

apps = []

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
        if cat in {"gd", "gp"}:
            return "game"
        if cat in {"ac", "ad", "al", "ap"}:
            return "app"
        if cat in {"gd", "gp"}:
            return "game"
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
                print(f"[!] PARAM_SFO not found in {pkg_path}")
                return {}, None

            tmp_root = pathlib.Path(tmpdir)
            sfo_path = tmp_root / "param.sfo"
            extract_pkg_entry(pkg_path, sfo_entry, sfo_path)
            info = parse_sfo_entries(sfo_path)

            icon_bytes = None
            if icon_entry is not None:
                icon_path = tmp_root / "icon0.png"
                try:
                    extract_pkg_entry(pkg_path, icon_entry, icon_path)
                except Exception as e:
                    print(f"[!] Error extracting ICON from {pkg_path}: {e}")
                else:
                    if icon_path.exists():
                        icon_bytes = icon_path.read_bytes()

            return info, icon_bytes
    except Exception as e:
        print(f"[!] Error reading PKG at {pkg_path}: {e}")
        return {}, None

for pkg in PKG_DIR.rglob("*.pkg"):
    info, icon_bytes = read_pkg_info(pkg)
    title = info.get("TITLE", pkg.stem)
    titleid = info.get("TITLE_ID", pkg.stem)
    version = info.get("VERSION", "1.00")
    category = info.get("CATEGORY")
    content_id = info.get("CONTENT_ID")
    app_type = parse_sfo_int(info.get("APP_TYPE"))
    apptype = map_apptype(category, app_type)
    region = region_from_content_id(content_id)

    if icon_bytes:
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        icon_out = ICONS_DIR / f"{titleid}.png"
        icon_out.write_bytes(icon_bytes)

    pkg_rel = pkg.relative_to(PKG_DIR).as_posix()
    pkg_url = f"{BASE_URL}/pkg/{quote(pkg_rel, safe='/')}"
    icon_url = f"{BASE_URL}/_media/icons/{quote(f'{titleid}.png')}"

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

with open(OUT, "w") as f:
    json.dump({"apps": apps}, f, indent=2)

print("[+] index.json generated")
