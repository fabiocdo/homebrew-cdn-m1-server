import shutil
from pathlib import Path

import settings
from utils.log_utils import log


def dry_run(pkgs, skip_paths=None):
    """Plan moves and report which entries can be moved."""
    plan = []
    skipped_conflict = []
    skipped_excluded = []
    conflict_sources = []
    skip_set = {str(path) for path in (skip_paths or [])}

    excluded = set()
    if settings.AUTO_MOVER_EXCLUDED_DIRS:
        parts = [part.strip() for part in settings.AUTO_MOVER_EXCLUDED_DIRS.split(",")]
        excluded = {part for part in parts if part}

    def is_excluded(path):
        return any(part in excluded for part in path.parts)

    def conflict_dir():
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        target = settings.DATA_DIR / "_errors"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def conflict_target_for(path):
        base = Path(path)
        target_dir = conflict_dir()
        candidate = target_dir / base.name
        counter = 1
        while candidate.exists():
            if base.suffix:
                candidate = target_dir / f"{base.stem}_{counter}{base.suffix}"
            else:
                candidate = target_dir / f"{base.name}_{counter}"
            counter += 1
        return candidate
    for pkg, data in pkgs:
        if "_conflict" in pkg.stem:
            target = conflict_target_for(pkg)
            try:
                shutil.move(str(pkg), str(target))
                log("warn", "Moved conflict file to _errors directory", module="AUTO_MOVER")
            except Exception:
                pass
            continue
        apptype = data.get("apptype")
        if apptype not in settings.APPTYPE_PATHS:
            continue
        if is_excluded(pkg):
            log("debug", f"Skipping move; source excluded: {pkg}", module="AUTO_MOVER")
            skipped_excluded.append(str(pkg))
            continue
        target_dir = settings.APPTYPE_PATHS[apptype]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pkg.name

        if pkg.resolve() == target_path.resolve():
            continue
        if is_excluded(target_path):
            log("debug", f"Skipping move; target excluded: {target_path}", module="AUTO_MOVER")
            skipped_excluded.append(str(pkg))
            continue
        if str(pkg) in skip_set:
            log(
                "warn",
                "Skipped move. A file with the same name already exists in the target directory",
                module="AUTO_MOVER",
            )
            continue
        if target_path.exists():
            skipped_conflict.append(str(target_path))
            conflict_sources.append(str(pkg))
            continue
        plan.append((pkg, target_path))

    return {
        "plan": plan,
        "skipped_conflict": skipped_conflict,
        "skipped_excluded": skipped_excluded,
        "conflict_sources": conflict_sources,
    }


def apply(dry_result):
    """Execute moves from a dry-run plan."""
    moved = []
    errors = []
    quarantined = []

    def quarantine_path(path):
        base = Path(path)
        if not base.exists():
            return None
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conflict_dir = settings.DATA_DIR / "_conflict"
        conflict_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_conflict"
        if base.suffix:
            stem = base.stem + suffix
            candidate = conflict_dir / f"{stem}{base.suffix}"
        else:
            candidate = conflict_dir / f"{base.name}{suffix}"
        counter = 1
        while candidate.exists():
            if base.suffix:
                candidate = conflict_dir / f"{base.stem}{suffix}_{counter}{base.suffix}"
            else:
                candidate = conflict_dir / f"{base.name}{suffix}_{counter}"
            counter += 1
        try:
            base.rename(candidate)
            return candidate
        except Exception:
            return None
    for pkg, target_path in dry_result.get("plan", []):
        try:
            shutil.move(str(pkg), str(target_path))
            moved.append((pkg, target_path))
        except Exception as e:
            errors.append((str(target_path), str(e)))

    if moved:
        log(
            "info",
            "Moved: " + "; ".join(f"{src} -> {dest}" for src, dest in moved),
            module="AUTO_MOVER",
        )
    for target in dry_result.get("skipped_conflict", []):
        log(
            "warn",
            "Skipped move. A file with the same name already exists in the target directory",
            module="AUTO_MOVER",
        )
    if errors:
        log(
            "error",
            f"Failed {len(errors)} move(s)",
            module="AUTO_MOVER",
        )

    touched_paths = []
    for src, dest in moved:
        touched_paths.extend([str(src), str(dest)])
    for source in dry_result.get("conflict_sources", []):
        target = quarantine_path(source)
        if target is not None:
            quarantined.append(str(target))
            touched_paths.extend([source, str(target)])
            log(
                "warn",
                "Quarantined file due to name conflict",
                module="AUTO_MOVER",
            )
    return {"moved": moved, "errors": errors, "touched_paths": touched_paths, "quarantined_paths": quarantined}


def run(pkgs, skip_paths=None):
    """Move PKGs into apptype folders when enabled."""
    return apply(dry_run(pkgs, skip_paths=skip_paths))
