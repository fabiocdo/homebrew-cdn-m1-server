import os
from pathlib import Path
from src.utils import PkgUtils, log
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.modules.models.watcher_models import PlanOutput
from src.utils.pkg_scanner import scan_pkgs


def plan_pkgs(
    pkg_utils: PkgUtils,
    formatter: AutoFormatter,
    sorter: AutoSorter,
) -> tuple[list[dict], dict[str, dict]]:
    log("info", "Detecting changes...", module="WATCHER_PLANNER")
    pkg_dir = Path(os.environ["PKG_DIR"])
    scan_results, has_changes = scan_pkgs(pkg_dir, pkg_utils)
    sfo_cache = {str(pkg): sfo for pkg, sfo in scan_results if sfo}
    if not has_changes:
        log("info", "No changes detected.", module="WATCHER_PLANNER")
        return [], sfo_cache
    log("info", "Changes detected.", module="WATCHER_PLANNER")
    log("info", "Planning changes...", module="WATCHER_PLANNER")

    results: list[dict] = []
    planned_paths: set[str] = set()
    planned_icons: set[str] = set()
    planned_renames = 0
    planned_moves = 0

    for pkg, sfo_data in scan_results:
        if not sfo_data:
            results.append({
                "source": str(pkg),
                "pkg": {"planned_path": str(pkg), "action": PlanOutput.REJECT, "reason": "missing_sfo"},
                "icon": {"planned_path": None, "action": PlanOutput.REJECT},
            })
            continue

        content_id = sfo_data.get("content_id", "")
        icon_path = pkg_utils.extract_pkg_icon(pkg, content_id, dry_run=True) if content_id else None

        formatter_result, planned_name = formatter.dry_run(pkg, sfo_data)
        planned_name = planned_name or pkg.name

        sorter_result, target_dir = sorter.dry_run(pkg, sfo_data.get("app_type", ""))
        planned_pkg_path = str((target_dir / planned_name) if target_dir else (pkg.parent / planned_name))

        planned_icon_path = str(icon_path) if icon_path else None
        current_pkg_path = str(pkg)
        planned_pkg_conflict = (
            Path(planned_pkg_path).exists() and planned_pkg_path != current_pkg_path
        ) or (
            planned_pkg_path in planned_paths and planned_pkg_path != current_pkg_path
        )

        reason = None
        if formatter_result == AutoFormatter.PlanResult.INVALID:
            planned_pkg_action = PlanOutput.REJECT
            reason = "formatter_invalid"
        elif planned_pkg_path == current_pkg_path:
            planned_pkg_action = PlanOutput.SKIP
        elif formatter_result == AutoFormatter.PlanResult.CONFLICT or sorter_result == AutoSorter.PlanResult.CONFLICT:
            planned_pkg_action = PlanOutput.REJECT
            reason = "formatter_conflict" if formatter_result == AutoFormatter.PlanResult.CONFLICT else "sorter_conflict"
        elif planned_pkg_conflict:
            planned_pkg_action = PlanOutput.REJECT
            reason = "planned_path_conflict"
        else:
            planned_pkg_action = PlanOutput.ALLOW
        planned_paths.add(planned_pkg_path)

        planned_icon_allowed = (
            planned_icon_path is not None
            and planned_icon_path not in planned_icons
            and not Path(planned_icon_path).exists()
        )
        if planned_icon_path:
            planned_icons.add(planned_icon_path)

        if planned_pkg_action == PlanOutput.ALLOW:
            if formatter_result == AutoFormatter.PlanResult.OK:
                planned_renames += 1
            if sorter_result == AutoSorter.PlanResult.OK:
                planned_moves += 1

        if planned_icon_path is None:
            icon_action = PlanOutput.REJECT
        elif Path(planned_icon_path).exists():
            icon_action = PlanOutput.SKIP
        elif planned_icon_allowed:
            icon_action = PlanOutput.ALLOW
        else:
            icon_action = PlanOutput.REJECT

        results.append({
            "source": str(pkg),
            "pkg": {
                "planned_path": planned_pkg_path,
                "action": planned_pkg_action,
                "reason": reason,
            },
            "icon": {
                "planned_path": planned_icon_path,
                "action": icon_action,
            },
        })

    planned_errors = sum(1 for item in results if item["pkg"]["action"] == PlanOutput.REJECT)
    planned_icons = sum(
        1 for item in results
        if item["icon"]["action"] == PlanOutput.ALLOW and item["pkg"]["action"] != PlanOutput.REJECT
    )
    planned_total = planned_moves + planned_renames + planned_icons + planned_errors
    log(
        "info",
        f"Changes planned: {planned_total} change(s) "
        f"(Moves: {planned_moves}, Renames: {planned_renames}, Extractions: {planned_icons}, Errors: {planned_errors})",
        module="WATCHER_PLANNER",
    )
    return results, sfo_cache
