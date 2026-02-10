# import os
# import threading
# from pathlib import Path
# import datetime
# from hb_store_m1.utils import PkgUtils
# from hb_store_m1.utils import log
# from src import AutoFormatter
# from hb_store_m1.modules.auto_sorter import AutoSorter
# from hb_store_m1.models import PlanOutput
#
#
# class WatcherExecutor:
#
#     def __init__(
#         self, pkg_utils: PkgUtils, formatter: AutoFormatter, sorter: AutoSorter
#     ):
#
#         self.pkg_utils = pkg_utils
#         self.formatter = formatter
#         self.sorter = sorter
#         self._error_log_lock = threading.Lock()
#
#     def run(
#         self,
#         results: list[dict],
#         sfo_cache: dict[str, dict],
#         log_start: bool = True,
#         log_summary: bool = True,
#         module_name: str = "WATCHER_EXECUTOR",
#     ) -> tuple[dict, dict]:
#
#         if log_start:
#             log("info", "Executing planned changes...", module=module_name)
#         error_dir = Path(os.environ["ERROR_DIR"])
#         error_dir.mkdir(parents=True, exist_ok=True)
#         log_dir = Path(os.environ.get("LOG_DIR", error_dir))
#         log_dir.mkdir(parents=True, exist_ok=True)
#
#         rejected = [
#             item for item in results if item["pkg"]["action"] == PlanOutput.REJECT
#         ]
#         icon_allowed = [
#             item
#             for item in results
#             if item["icon"]["action"] == PlanOutput.ALLOW
#             and item["pkg"]["action"] != PlanOutput.REJECT
#         ]
#         pkg_allowed = [
#             item for item in results if item["pkg"]["action"] == PlanOutput.ALLOW
#         ]
#
#         moved_to_error = 0
#         for item in rejected:
#             pkg_path = Path(item["source"])
#             if not pkg_path.exists():
#                 continue
#             conflict_path = error_dir / pkg_path.name
#             counter = 1
#             while conflict_path.exists():
#                 conflict_path = (
#                     error_dir / f"{pkg_path.stem}_{counter}{pkg_path.suffix}"
#                 )
#                 counter += 1
#             pkg_path.rename(conflict_path)
#             log(
#                 "warn",
#                 "PKG moved to errors folder",
#                 message=f"{pkg_path} -> {conflict_path}",
#                 module=module_name,
#             )
#             reason = item.get("pkg", {}).get("reason") or "unknown"
#             log_path = log_dir / "errors.log"
#             timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
#                 "%Y-%m-%d %H:%M:%S UTC"
#             )
#             line = (
#                 f"{timestamp} | reason={reason} | "
#                 f"source={item['source']} | planned_path={item['pkg']['planned_path']} | "
#                 f"moved_to={conflict_path}\n"
#             )
#             log_path.parent.mkdir(parents=True, exist_ok=True)
#             with self._error_log_lock:
#                 with log_path.open("a", encoding="utf-8") as handle:
#                     handle.write(line)
#             moved_to_error += 1
#
#         icons_extracted = 0
#         icon_failed = set()
#         for item in icon_allowed:
#             pkg_path = Path(item["source"])
#             icon_log_path = item["icon"]["planned_path"] or ""
#             log("debug", "Extracting icon", message=icon_log_path, module=module_name)
#             sfo_data = sfo_cache.get(str(pkg_path))
#             if not sfo_data:
#                 continue
#             content_id = sfo_data.get("content_id", "")
#             if not content_id:
#                 continue
#             planned_icon = item["icon"]["planned_path"]
#             pre_exists = Path(planned_icon).exists() if planned_icon else False
#             extracted_path = self.pkg_utils.extract_pkg_icon(
#                 pkg_path, content_id, dry_run=False
#             )
#             if extracted_path and extracted_path.exists():
#                 if not self.pkg_utils.is_valid_png(extracted_path):
#                     try:
#                         extracted_path.unlink()
#                     except Exception:
#                         pass
#                     icon_failed.add(item["source"])
#                     log(
#                         "error",
#                         "Invalid icon extracted",
#                         message=str(pkg_path),
#                         module=module_name,
#                     )
#                     continue
#                 if self.pkg_utils.optimize_png(extracted_path):
#                     log(
#                         "debug",
#                         "Icon optimized",
#                         message=str(extracted_path),
#                         module="WATCHER_EXECUTOR",
#                     )
#                 if not pre_exists:
#                     icons_extracted += 1
#                     log(
#                         "info",
#                         "Icon extracted",
#                         message=str(extracted_path),
#                         module=module_name,
#                     )
#             else:
#                 icon_failed.add(item["source"])
#                 log(
#                     "error",
#                     "Failed to extract icon",
#                     message=str(pkg_path),
#                     module=module_name,
#                 )
#
#         if icon_failed:
#             for source in icon_failed:
#                 pkg_path = Path(source)
#                 if not pkg_path.exists():
#                     continue
#                 conflict_path = error_dir / pkg_path.name
#                 counter = 1
#                 while conflict_path.exists():
#                     conflict_path = (
#                         error_dir / f"{pkg_path.stem}_{counter}{pkg_path.suffix}"
#                     )
#                     counter += 1
#                 pkg_path.rename(conflict_path)
#                 log(
#                     "warn",
#                     "PKG moved to errors folder",
#                     message=f"{pkg_path} -> {conflict_path}",
#                     module=module_name,
#                 )
#                 reason = "icon_extract_failed"
#                 log_path = log_dir / "errors.log"
#                 timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
#                     "%Y-%m-%d %H:%M:%S UTC"
#                 )
#                 line = (
#                     f"{timestamp} | reason={reason} | "
#                     f"source={source} | planned_path=icon_extract_failed | "
#                     f"moved_to={conflict_path}\n"
#                 )
#                 log_path.parent.mkdir(parents=True, exist_ok=True)
#                 with self._error_log_lock:
#                     with log_path.open("a", encoding="utf-8") as handle:
#                         handle.write(line)
#                 moved_to_error += 1
#
#         renamed_count = 0
#         moved_count = 0
#         for item in pkg_allowed:
#             if item["source"] in icon_failed:
#                 continue
#             pkg_path = Path(item["source"])
#             log(
#                 "debug",
#                 "Processing PKG for format/sort",
#                 message=str(pkg_path),
#                 module=module_name,
#             )
#             sfo_data = sfo_cache.get(str(pkg_path))
#             if not sfo_data:
#                 continue
#             new_name = self.formatter.run(pkg_path, sfo_data)
#             if new_name:
#                 renamed_count += 1
#             sorter_path = pkg_path if not new_name else pkg_path.with_name(new_name)
#             moved_path = self.sorter.run(sorter_path, sfo_data.get("app_type", ""))
#             if moved_path:
#                 moved_count += 1
#
#         rejected_sources = {
#             item["source"]
#             for item in results
#             if item["pkg"]["action"] == PlanOutput.REJECT
#         }
#         skipped_sources = {
#             item["source"]
#             for item in results
#             if item["pkg"]["action"] == PlanOutput.SKIP
#             or item["icon"]["action"] == PlanOutput.SKIP
#         }
#         skipped_count = len(skipped_sources - rejected_sources)
#         if log_summary:
#             log(
#                 "info",
#                 f"Planned changes executed: Moves: {moved_count}, Renames: {renamed_count}, "
#                 f"Extractions: {icons_extracted}, Errors: {moved_to_error}, Skipped: {skipped_count}",
#                 module=module_name,
#             )
#
#         stats = {
#             "moves": moved_count,
#             "renames": renamed_count,
#             "extractions": icons_extracted,
#             "errors": moved_to_error,
#             "skipped": skipped_count,
#         }
#         return sfo_cache, stats
