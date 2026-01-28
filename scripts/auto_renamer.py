import re

import settings
from utils.log_utils import log


def run(pkgs):
    """Rename PKGs based on SFO metadata."""
    def format_pkg_name(template, data):
        safe = {}
        for key, value in data.items():
            if value is None:
                safe[key] = ""
            elif key == "title":
                title_value = str(value)
                if settings.AUTO_RENAMER_MODE == "uppercase":
                    title_value = title_value.upper()
                elif settings.AUTO_RENAMER_MODE == "lowercase":
                    title_value = title_value.lower()
                elif settings.AUTO_RENAMER_MODE == "capitalize":
                    title_value = " ".join(part.capitalize() for part in value.split())
                title_value = re.sub(r"([A-Za-z])([0-9])", r"\1_\2", title_value)
                value_str = title_value
            else:
                value_str = str(value)
            value_str = re.sub(r"[\/\\:-]+", "_", value_str)
            value_str = re.sub(r"[^A-Za-z0-9 _!\[\]\(\)\.']+", "_", value_str).strip()
            value_str = "_".join(part for part in value_str.split() if part)
            while "__" in value_str:
                value_str = value_str.replace("__", "_")
            safe[key] = value_str
        name = template.format_map(safe).strip()
        if not name.lower().endswith(".pkg"):
            name = f"{name}.pkg"
        return name

    def rename_pkg(pkg_path, title, titleid, apptype, region, version, category, content_id, app_type):
        if not titleid:
            return pkg_path
        new_name = format_pkg_name(
            settings.AUTO_RENAMER_TEMPLATE,
            {
                "title": title,
                "titleid": titleid,
                "version": version,
                "category": category,
                "content_id": content_id,
                "app_type": app_type,
                "apptype": apptype,
                "region": region,
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

    for pkg, data in pkgs:
        rename_pkg(
            pkg,
            data.get("title"),
            data.get("titleid"),
            data.get("apptype"),
            data.get("region"),
            data.get("version"),
            data.get("category"),
            data.get("content_id"),
            data.get("app_type"),
        )
