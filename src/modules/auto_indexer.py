import os
from pathlib import Path
from src.utils import PkgUtils, log
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter


class AutoIndexer:
    """
    AutoIndexer handles the creation and maintenance of the store index.
    """

    def __init__(self):
        """
        Initialize the indexer.
        """
        pass

    def dry_run(self) -> list[dict]:
        """
        Plan the indexing process for all PKGs without applying changes.
        """
        log("info", "Planning changes...", module="AUTO_INDEXER")
        pkg_dir = Path(os.environ["PKG_DIR"])
        pkg_utils = PkgUtils()
        formatter = AutoFormatter()
        sorter = AutoSorter()
        results = []
        planned_paths = set()
        planned_icons = set()
        planned_renames = 0
        planned_moves = 0
        for pkg in pkg_dir.rglob("*.pkg"):
            sfo_result, sfo_payload = pkg_utils.extract_pkg_data(pkg)
            if sfo_result != PkgUtils.ExtractResult.OK:
                results.append({
                    "source_pkg_path": str(pkg),
                    "planned_pkg_path": str(pkg),
                    "planned_icon_path": None,
                    "planned_pkg_output": "rejected",
                    "planned_icon_output": "rejected",
                })
                continue

            sfo_data = sfo_payload
            content_id = sfo_data.get("content_id", "")
            icon_result, icon_path = (
                pkg_utils.extract_pkg_icon(pkg, content_id, dry_run=True)
                if content_id
                else (PkgUtils.ExtractResult.NOT_FOUND, str(pkg))
            )

            formatter_result, planned_name = formatter.dry_run(pkg, sfo_data)
            planned_name = planned_name or pkg.name

            sorter_result, target_dir = sorter.dry_run(pkg, sfo_data.get("app_type", ""))
            planned_pkg_path = str((target_dir / planned_name) if target_dir else (pkg.parent / planned_name))

            planned_icon_path = icon_path if icon_result in (PkgUtils.ExtractResult.OK, PkgUtils.ExtractResult.SKIP) else None
            current_pkg_path = str(pkg)
            planned_pkg_conflict = (
                Path(planned_pkg_path).exists() and planned_pkg_path != current_pkg_path
            ) or (
                planned_pkg_path in planned_paths and planned_pkg_path != current_pkg_path
            )
            if formatter_result == AutoFormatter.PlanResult.INVALID:
                planned_pkg_output = "rejected"
            elif planned_pkg_path == current_pkg_path:
                planned_pkg_output = "skip"
            elif formatter_result == AutoFormatter.PlanResult.CONFLICT or sorter_result == AutoSorter.PlanResult.CONFLICT:
                planned_pkg_output = "rejected"
            elif planned_pkg_conflict:
                planned_pkg_output = "rejected"
            else:
                planned_pkg_output = "allowed"
            planned_paths.add(planned_pkg_path)

            planned_icon_allowed = (
                icon_result == PkgUtils.ExtractResult.OK
                and planned_icon_path is not None
                and planned_icon_path not in planned_icons
                and not Path(planned_icon_path).exists()
            )
            if planned_icon_path:
                planned_icons.add(planned_icon_path)

            if planned_pkg_output == "allowed":
                if formatter_result == AutoFormatter.PlanResult.OK:
                    planned_renames += 1
                if sorter_result == AutoSorter.PlanResult.OK:
                    planned_moves += 1

            results.append({
                "source_pkg_path": str(pkg),
                "planned_pkg_path": planned_pkg_path,
                "planned_icon_path": planned_icon_path,
                "planned_pkg_output": planned_pkg_output,
                "planned_icon_output": (
                    "skip" if icon_result == PkgUtils.ExtractResult.SKIP
                    else "allowed" if planned_icon_allowed
                    else "rejected"
                ),
            })
        planned_errors = sum(1 for item in results if item["planned_pkg_output"] == "rejected")
        planned_icons = sum(
            1 for item in results
            if item["planned_icon_output"] == "allowed" and item["planned_pkg_output"] != "rejected"
        )
        planned_total = planned_moves + planned_renames + planned_icons + planned_errors
        log(
            "info",
            f"Planning complete: {planned_total} change(s) planned "
            f"(Moves: {planned_moves}, Renames: {planned_renames}, Extractions: {planned_icons}, Errors: {planned_errors})",
            module="AUTO_INDEXER",
        )
        return results

    def run(self):
        """
        Execute the indexing process.
        """
        results = self.dry_run()

        log("info", "Executing planned changes...", module="AUTO_INDEXER")
        error_dir = Path(os.environ["ERROR_DIR"])
        error_dir.mkdir(parents=True, exist_ok=True)
        pkg_utils = PkgUtils()
        formatter = AutoFormatter()
        sorter = AutoSorter()

        rejected = [
            item for item in results
            if item["planned_pkg_output"] == "rejected"
        ]
        icon_allowed = [
            item for item in results
            if item["planned_icon_output"] == "allowed" and item["planned_pkg_output"] != "rejected"
        ]
        pkg_allowed = [item for item in results if item["planned_pkg_output"] == "allowed"]

        moved_to_error = 0
        for item in rejected:
            pkg_path = Path(item["source_pkg_path"])
            if not pkg_path.exists():
                continue
            log("debug", "Moving rejected PKG to errors", message=str(pkg_path), module="AUTO_INDEXER")
            conflict_path = error_dir / pkg_path.name
            counter = 1
            while conflict_path.exists():
                conflict_path = error_dir / f"{pkg_path.stem}_{counter}{pkg_path.suffix}"
                counter += 1
            pkg_path.rename(conflict_path)
            moved_to_error += 1

        sfo_cache = {}
        icons_extracted = 0
        for item in icon_allowed:
            pkg_path = Path(item["source_pkg_path"])
            icon_log_path = item.get("planned_icon_path") or ""
            log("debug", "Extracting icon", message=icon_log_path, module="AUTO_INDEXER")
            if pkg_path not in sfo_cache:
                sfo_result, sfo_payload = pkg_utils.extract_pkg_data(pkg_path)
                if sfo_result != PkgUtils.ExtractResult.OK:
                    continue
                sfo_cache[pkg_path] = sfo_payload
            sfo_data = sfo_cache[pkg_path]
            content_id = sfo_data.get("content_id", "")
            if not content_id:
                continue
            icon_result, _ = pkg_utils.extract_pkg_icon(pkg_path, content_id, dry_run=False)
            if icon_result == PkgUtils.ExtractResult.OK:
                icons_extracted += 1

        renamed_count = 0
        moved_count = 0
        for item in pkg_allowed:
            pkg_path = Path(item["source_pkg_path"])
            log("debug", "Processing PKG for format/sort", message=str(pkg_path), module="AUTO_INDEXER")
            if pkg_path not in sfo_cache:
                sfo_result, sfo_payload = pkg_utils.extract_pkg_data(pkg_path)
                if sfo_result != PkgUtils.ExtractResult.OK:
                    continue
                sfo_cache[pkg_path] = sfo_payload
            sfo_data = sfo_cache[pkg_path]
            new_name = formatter.run(pkg_path, sfo_data)
            if new_name:
                renamed_count += 1
            sorter_path = pkg_path if not new_name else pkg_path.with_name(new_name)
            moved_path = sorter.run(sorter_path, sfo_data.get("app_type", ""))
            if moved_path:
                moved_count += 1

        skipped_count = sum(1 for item in results if item["planned_pkg_output"] == "skip")
        log(
            "info",
            f"Planned changes executed: Moves: {moved_count}, Renames: {renamed_count}, Extractions: {icons_extracted}, Errors: {moved_to_error}, Skipped: {skipped_count}",
            module="AUTO_INDEXER",
        )
