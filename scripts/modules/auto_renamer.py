import re
from pathlib import Path

import settings
from utils.log_utils import format_log_line, log


def dry_run(pkgs):
    """Plan renames and report which entries can be renamed."""
    planned = {}
    blocked = set()
    blocked_sources = set()
    conflict_sources = set()
    conflicted = set()
    excluded_dirs = set()
    excluded_sources = set()
    if settings.AUTO_RENAMER_EXCLUDED_DIRS:
        parts = [part.strip() for part in settings.AUTO_RENAMER_EXCLUDED_DIRS.split(",")]
        excluded_dirs = {part for part in parts if part}

    def is_excluded(path):
        return any(part in excluded_dirs for part in path.parts)

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
            return pkg_path, None, "missing_titleid"
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
            return pkg_path, None, "already_named"
        target_path = pkg_path.with_name(new_name)
        return pkg_path, target_path, "rename"

    error_sources = set()
    for pkg, data in pkgs:
        source_path, target_path, status = planned_rename(
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
        if status == "missing_titleid":
            error_sources.add(source_path)
            blocked_sources.add(source_path)
            continue
        if target_path is None:
            continue
        if is_excluded(source_path):
            log("debug", f"Skipping rename; source excluded: {source_path}", module="AUTO_RENAMER")
            excluded_sources.add(source_path)
            continue
        if is_excluded(target_path):
            log("debug", f"Skipping rename; target excluded: {target_path}", module="AUTO_RENAMER")
            excluded_sources.add(source_path)
            continue
        apptype = data.get("apptype")
        apptype_dir = settings.APPTYPE_PATHS.get(apptype) if apptype else None
        if apptype_dir and not is_excluded(apptype_dir):
            apptype_target = apptype_dir / target_path.name
            if apptype_target.exists():
                blocked.add(apptype_target)
                blocked_sources.add(source_path)
                conflict_sources.add(source_path)
                continue
        if apptype_dir and is_excluded(apptype_dir):
            log("debug", f"Skipping rename; apptype dir excluded: {apptype_dir}", module="AUTO_RENAMER")
            excluded_sources.add(source_path)
        if target_path.exists():
            blocked.add(target_path)
            blocked_sources.add(source_path)
            conflict_sources.add(source_path)
            continue
        planned.setdefault(target_path, []).append(source_path)

    plan = []
    for target_path, sources in planned.items():
        if target_path in blocked:
            blocked_sources.update(sources)
            conflict_sources.update(sources)
            continue
        if len(sources) > 1:
            conflicted.add(target_path)
            blocked_sources.update(sources)
            conflict_sources.update(sources)
            continue
        plan.append((sources[0], target_path))

    return {
        "plan": plan,
        "blocked_sources": [str(path) for path in (blocked_sources | excluded_sources | error_sources)],
        "skipped_conflict": [str(path) for path in (blocked | conflicted)],
        "conflict_sources": [str(path) for path in conflict_sources],
        "error_sources": [str(path) for path in error_sources],
        "skipped_excluded": len(excluded_sources),
    }


def apply(dry_result):
    """Execute renames from a dry-run plan."""
    renamed = []
    quarantined = []

    def append_error_log(error_dir, message):
        try:
            log_path = error_dir / "error_log.txt"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(format_log_line(message, module="AUTO_RENAMER") + "\n")
        except Exception:
            pass

    def quarantine_path(path):
        base = Path(path)
        if not base.exists():
            return None
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conflict_dir = settings.DATA_DIR / "_errors"
        conflict_dir.mkdir(parents=True, exist_ok=True)
        candidate = conflict_dir / base.name
        counter = 1
        while candidate.exists():
            if base.suffix:
                candidate = conflict_dir / f"{base.stem}_{counter}{base.suffix}"
            else:
                candidate = conflict_dir / f"{base.name}_{counter}"
            counter += 1
        try:
            base.rename(candidate)
            return candidate
        except Exception:
            return None
    for source_path, target_path in dry_result.get("plan", []):
        try:
            source_path.rename(target_path)
            renamed.append((source_path, target_path))
        except Exception:
            continue

    for src, dest in renamed:
        log(
            "info",
            f"Renamed: {src} -> {dest}",
            module="AUTO_RENAMER",
        )
    for target in dry_result.get("skipped_conflict", []):
        log(
            "warn",
            "Skipped rename. A file with the same name already exists in the target directory",
            module="AUTO_RENAMER",
        )

    touched_paths = []
    for old_path, new_path in renamed:
        touched_paths.extend([str(old_path), str(new_path)])
    for source in dry_result.get("conflict_sources", []):
        target = quarantine_path(source)
        if target is not None:
            quarantined.append(str(target))
            touched_paths.extend([source, str(target)])
            message = f"Moved file with error to {settings.DATA_DIR / '_errors'}: {source}"
            log("warn", message, module="AUTO_RENAMER")
            append_error_log(settings.DATA_DIR / "_errors", message)
    for source in dry_result.get("error_sources", []):
        target = quarantine_path(source)
        if target is not None:
            quarantined.append(str(target))
            touched_paths.extend([source, str(target)])
            message = f"Moved file with error to {settings.DATA_DIR / '_errors'}: {source}"
            log("warn", message, module="AUTO_RENAMER")
            append_error_log(settings.DATA_DIR / "_errors", message)
    return {"renamed": renamed, "touched_paths": touched_paths, "quarantined_paths": quarantined}


def run(pkgs):
    """Rename PKGs based on SFO metadata."""
    return apply(dry_run(pkgs))
