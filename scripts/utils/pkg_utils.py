import pathlib
import tempfile

import settings
from utils.log_utils import log
from tools.pkgtool import run_pkgtool


def extract_pkg_data(pkg_path, include_icon=False):
    """Extract and normalize PKG metadata, optionally including icon bytes."""

    def process_entries(entries_output):
        sfo_entry = None
        icon_entry = None
        for line in entries_output.splitlines():
            line = line.strip()
            if not line or line.startswith("Offset"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            entry_id = parts[3]
            name = parts[5] if len(parts) >= 6 else parts[4]
            lower = name.lower()
            normalized = lower.replace(".", "_")
            if "param_sfo" in normalized:
                sfo_entry = entry_id
            elif normalized in {"icon0_png", "icon0_00_png", "pic0_png"}:
                if icon_entry is None or normalized == "icon0_png":
                    icon_entry = entry_id
        return sfo_entry, icon_entry

    def process_info(sfo_path):
        output = run_pkgtool(["sfo_listentries", str(sfo_path)])
        info = {}
        for line in output.splitlines():
            if " = " not in line or " : " not in line:
                continue
            left, value = line.split(" = ", 1)
            name = left.split(" : ", 1)[0].strip()
            info[name] = value.strip()
        return info

    def process_app_type(info):
        if "APP_TYPE" not in info:
            return
        value = info["APP_TYPE"]
        if isinstance(value, int):
            info["APP_TYPE"] = value
            return
        if not value:
            info["APP_TYPE"] = None
            return
        value_str = str(value)
        if value_str.startswith("0x"):
            try:
                info["APP_TYPE"] = int(value_str, 16)
            except ValueError:
                info["APP_TYPE"] = None
            return
        try:
            info["APP_TYPE"] = int(value_str)
        except ValueError:
            info["APP_TYPE"] = None

    def process_apptype(info):
        category = info.get("CATEGORY")
        app_type = info.get("APP_TYPE")
        apptype = "app"
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
                apptype = category_map[cat]
            elif app_type == 2:
                apptype = "game"
        elif app_type == 2:
            apptype = "game"
        info["APPTYPE"] = apptype

    def process_region(info):
        content_id = info.get("CONTENT_ID")
        if not content_id or len(content_id) < 2:
            return
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
        info["REGION"] = region_map.get(prefix, prefix)

    def process_icon_bytes(icon_entry, tmp_root):
        if not include_icon or icon_entry is None:
            return None
        icon_path = tmp_root / "icon0.png"
        run_pkgtool(["pkg_extractentry", str(pkg_path), str(icon_entry), str(icon_path)])
        if icon_path.exists():
            return icon_path.read_bytes()
        return None

    def build_data(info):
        title = info.get("TITLE")
        titleid = info.get("TITLE_ID")
        version = info.get("VERSION")
        category = info.get("CATEGORY")
        content_id = info.get("CONTENT_ID")
        app_type = info.get("APP_TYPE")
        apptype = info.get("APPTYPE")
        region = info.get("REGION")

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

    with tempfile.TemporaryDirectory(prefix="pkg_extract_") as tmpdir:
        tmp_root = pathlib.Path(tmpdir)
        entries_output = run_pkgtool(["pkg_listentries", str(pkg_path)])
        sfo_entry, icon_entry = process_entries(entries_output)

        if sfo_entry is None:
            raise RuntimeError(f"PARAM_SFO not found in {pkg_path}")

        sfo_path = tmp_root / "param.sfo"
        run_pkgtool(["pkg_extractentry", str(pkg_path), str(sfo_entry), str(sfo_path)])
        if not sfo_path.exists():
            raise RuntimeError(f"PARAM_SFO not found in {pkg_path}")

        info = process_info(sfo_path)
        process_app_type(info)
        process_apptype(info)
        process_region(info)
        icon_bytes = process_icon_bytes(icon_entry, tmp_root)

        data = build_data(info)
        return {"data": data, "icon_bytes": icon_bytes}


def scan_pkgs():
    """Yield (pkg_path, data) for every PKG under PKG_DIR."""
    for pkg in settings.PKG_DIR.rglob("*.pkg"):
        if any(part.startswith("_") for part in pkg.parts):
            continue
        try:
            result = extract_pkg_data(pkg, include_icon=False)
        except Exception as e:
            log("error", f"Failed to read PKG metadata: {pkg} ({e})")
            continue
        yield pkg, result["data"]
