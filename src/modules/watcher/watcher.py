import time
from src.utils import log
from src import settings
from src.modules.auto_formatter.auto_formatter import AutoFormatter
from src.modules.auto_sorter.auto_sorter import AutoSorter
from src.modules.auto_indexer.auto_indexer import AutoIndexer


class Watcher:
    """
    Watcher orchestrates AutoFormatter, AutoSorter, and AutoIndexer modules.

    It runs periodic scans and processes PKG files through the automation pipeline.
    """

    def __init__(
        self,
        pkg_watcher_enabled: bool = False,
        auto_indexer_enabled: bool = False,
        auto_formatter_enabled: bool = False,
        auto_sorter_enabled: bool = False,
        periodic_scan_seconds: int = 30,
    ):
        """
        Initialize the Watcher with configuration.

        :param pkg_watcher_enabled: Whether the watcher is active
        :param auto_indexer_enabled: Whether to run the indexer
        :param auto_formatter_enabled: Whether to run the formatter
        :param auto_sorter_enabled: Whether to run the sorter
        :param periodic_scan_seconds: Seconds between periodic scans
        """
        self.pkg_watcher_enabled = pkg_watcher_enabled
        self.auto_indexer_enabled = auto_indexer_enabled
        self.auto_formatter_enabled = auto_formatter_enabled
        self.auto_sorter_enabled = auto_sorter_enabled
        self.periodic_scan_seconds = periodic_scan_seconds

        # Initialize orchestrated modules
        self.formatter = AutoFormatter(
            template=settings.AUTO_FORMATTER_TEMPLATE,
            mode=settings.AUTO_FORMATTER_MODE
        )
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
