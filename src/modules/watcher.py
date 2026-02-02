import os
import time
from src.utils import PkgUtils, log
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.modules.auto_indexer import AutoIndexer
from src.modules.helpers.watcher_planner import plan_pkgs
from src.modules.helpers.watcher_executor import execute_plan


class Watcher:
    """
    Watcher orchestrates AutoFormatter, AutoSorter, and AutoIndexer modules.

    It runs periodic scans and processes PKG files through the automation pipeline.
    """

    def __init__(self):
        self.pkg_watcher_enabled = os.environ["PKG_WATCHER_ENABLED"].lower() == "true"
        self.auto_indexer_enabled = os.environ["AUTO_INDEXER_ENABLED"].lower() == "true"
        self.auto_formatter_enabled = os.environ["AUTO_FORMATTER_ENABLED"].lower() == "true"
        self.auto_sorter_enabled = os.environ["AUTO_SORTER_ENABLED"].lower() == "true"
        self.periodic_scan_seconds = int(os.environ["PKG_WATCHER_PERIODIC_SCAN_SECONDS"])

        self.pkg_utils = PkgUtils()
        self.formatter = AutoFormatter()
        self.sorter = AutoSorter()
        self.indexer = AutoIndexer()

    def start(self):
        """
        Execute the watcher pipeline once.
        """
        if not self.pkg_watcher_enabled:
            log("info", "Watcher is disabled. Skipping...", module="WATCHER")
            return
        interval = max(1, self.periodic_scan_seconds)
        log("info", f"Watcher started (interval: {interval}s)", module="WATCHER")
        next_run = time.monotonic()
        while True:
            now = time.monotonic()
            if now < next_run:
                time.sleep(next_run - now)
            start = time.monotonic()
            try:
                results, sfo_cache = plan_pkgs(self.pkg_utils, self.formatter, self.sorter)
                if not results:
                    next_run = start + interval
                    continue
                sfo_cache, _stats = execute_plan(
                    results,
                    sfo_cache,
                    self.pkg_utils,
                    self.formatter,
                    self.sorter,
                )
                if self.auto_indexer_enabled:
                    self.indexer.run(results, sfo_cache)
            except Exception as exc:
                log("error", "Watcher cycle failed", message=str(exc), module="WATCHER")
            next_run = start + interval
