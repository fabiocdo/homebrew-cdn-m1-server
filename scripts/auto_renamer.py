import re

import settings
from utils.log_utils import log


def run(pkgs):
    """Rename PKGs based on SFO metadata."""
    renamed = []
    planned = {}
    blocked = set()
    conflicted = set()

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

    def planned_rename(pkg_path, title, titleid, apptype, region, version, category, content_id, app_type):
        if not titleid:
            return pkg_path, None
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
            return pkg_path, None
        target_path = pkg_path.with_name(new_name)
        return pkg_path, target_path

    for pkg, data in pkgs:
        source_path, target_path = planned_rename(
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
        if target_path is None:
            continue
        if target_path.exists():
            blocked.add(target_path)
            continue
        planned.setdefault(target_path, []).append(source_path)

    for target_path, sources in planned.items():
        if target_path in blocked:
            continue
        if len(sources) > 1:
            conflicted.add(target_path)
            continue
        source_path = sources[0]
        try:
            source_path.rename(target_path)
            renamed.append((source_path, target_path))
        except Exception:
            continue

    if renamed:
        log(
            "info",
            "Renamed: " + "; ".join(f"{src} -> {dest}" for src, dest in renamed),
            module="AUTO_RENAMER",
        )
    if blocked:
        log(
            "warn",
            f"Skipped {len(blocked)} rename(s); target already exists",
            module="AUTO_RENAMER",
        )
    if conflicted:
        log(
            "warn",
            f"Skipped {len(conflicted)} rename(s); conflicting targets",
            module="AUTO_RENAMER",
        )

    touched_paths = []
    for old_path, new_path in renamed:
        touched_paths.extend([str(old_path), str(new_path)])
    return {"renamed": renamed, "touched_paths": touched_paths}
