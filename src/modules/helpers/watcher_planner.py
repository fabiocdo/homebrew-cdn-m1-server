from __future__ import annotations

import os
from pathlib import Path
from src.utils import PkgUtils, log
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.modules.models.watcher_models import PlanOutput
from src.utils.pkg_scanner import scan_pkgs


class WatcherPlanner:
    """
    Plans PKG changes using the current filesystem and cache state.

    :param pkg_utils: PkgUtils instance
    :param formatter: AutoFormatter instance
    :param sorter: AutoSorter instance
    :return: None
    """

    def __init__(self, pkg_utils: PkgUtils, formatter: AutoFormatter, sorter: AutoSorter):
        """
        Initialize planner dependencies.

        :param pkg_utils: PkgUtils instance
        :param formatter: AutoFormatter instance
        :param sorter: AutoSorter instance
        :return: None
        """
        self.pkg_utils = pkg_utils
        self.formatter = formatter
        self.sorter = sorter

    def plan(self) -> tuple[list[dict], dict[str, dict]]:
        """
        Plan changes for all PKGs.

        :param: None
        :return: Tuple of (planned items, SFO cache)
        """
        log("info", "Detecting changes...", module="WATCHER_PLANNER")
        pkg_dir = Path(os.environ["PKG_DIR"])
        pkg_list = list(pkg_dir.rglob("*.pkg"))
        log("info", f"Scanning {len(pkg_list)} PKG(s) for changes...", module="WATCHER_PLANNER")
        batch_size = int(os.environ.get("WATCHER_SCAN_BATCH_SIZE", "50"))
        workers = int(os.environ.get("WATCHER_SCAN_WORKERS", "4"))
        if workers < 1:
            workers = 1
        if batch_size < 1:
            batch_size = None
        scan_results, has_changes = scan_pkgs(
            pkg_dir,
            self.pkg_utils,
            pkg_list,
            batch_size=batch_size,
            workers=workers,
            log_module="WATCHER_PLANNER",
        )
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
            icon_path = self.pkg_utils.extract_pkg_icon(pkg, content_id, dry_run=True) if content_id else None
            icon_invalid = False
            if icon_path and Path(icon_path).exists():
                icon_invalid = not self.pkg_utils.is_valid_png(Path(icon_path))
            missing_icon = icon_path is None

            formatter_result, planned_name = self.formatter.dry_run(pkg, sfo_data)
            planned_name = planned_name or pkg.name

            sorter_result, target_dir = self.sorter.dry_run(pkg, sfo_data.get("app_type", ""))
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
            if planned_pkg_action != PlanOutput.REJECT and (missing_icon or icon_invalid):
                planned_pkg_action = PlanOutput.REJECT
                reason = "missing_icon" if missing_icon else "invalid_icon"
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

            if icon_invalid:
                icon_action = PlanOutput.REJECT
            elif planned_icon_path is None:
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
