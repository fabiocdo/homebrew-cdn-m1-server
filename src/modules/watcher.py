import os
from src.utils import log
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.modules.auto_indexer import AutoIndexer


class Watcher:
    """
    Watcher orchestrates AutoFormatter, AutoSorter, and AutoIndexer modules.

    It runs periodic scans and processes PKG files through the automation pipeline.
    """

    def __init__(
        self,
        pkg_watcher_enabled: bool | None = None,
        auto_indexer_enabled: bool | None = None,
        auto_formatter_enabled: bool | None = None,
        auto_sorter_enabled: bool | None = None,
        periodic_scan_seconds: int | None = None,
    ):
        """
        Initialize the Watcher with configuration.

        :param pkg_watcher_enabled: Whether the watcher is active
        :param auto_indexer_enabled: Whether to run the indexer
        :param auto_formatter_enabled: Whether to run the formatter
        :param auto_sorter_enabled: Whether to run the sorter
        :param periodic_scan_seconds: Seconds between periodic scans
        """
        self.pkg_watcher_enabled = (
            os.getenv("PKG_WATCHER_ENABLED", "false").lower() == "true"
            if pkg_watcher_enabled is None
            else pkg_watcher_enabled
        )
        self.auto_indexer_enabled = (
            os.getenv("AUTO_INDEXER_ENABLED", "false").lower() == "true"
            if auto_indexer_enabled is None
            else auto_indexer_enabled
        )
        self.auto_formatter_enabled = (
            os.getenv("AUTO_FORMATTER_ENABLED", "false").lower() == "true"
            if auto_formatter_enabled is None
            else auto_formatter_enabled
        )
        self.auto_sorter_enabled = (
            os.getenv("AUTO_SORTER_ENABLED", "false").lower() == "true"
            if auto_sorter_enabled is None
            else auto_sorter_enabled
        )
        self.periodic_scan_seconds = (
            int(os.getenv("PERIODIC_SCAN_SECONDS", "30"))
            if periodic_scan_seconds is None
            else periodic_scan_seconds
        )

        # Initialize orchestrated modules
        self.formatter = AutoFormatter()
        self.sorter = AutoSorter()
        self.indexer = AutoIndexer()

    def run(self):
        """
        Start the watcher loop.
        """
        if not self.pkg_watcher_enabled:
            log("info", "Watcher is disabled. Skipping...", module="WATCHER")
            return

        log("info", f"Starting Watcher (interval: {self.periodic_scan_seconds}s)", module="WATCHER")
        
        # TODO: Implement the orchestration loop
        pass
