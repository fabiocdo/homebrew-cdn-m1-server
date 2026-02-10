import os
import re
import time
import threading
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from hb_store_m1.utils import PkgUtils
from hb_store_m1.utils import log
from src import UpdateFetcher
from src import AutoFormatter
from hb_store_m1.modules.auto_sorter import AutoSorter
from src import AutoIndexer
from src import WatcherPlanner
from hb_store_m1.helpers.watcher_executor import WatcherExecutor

from src import global_files, global_envs, global_paths


class Watcher:

    def __init__(self):

        self._access_log_offset = 0
        self._access_log_since = None
        self._access_log_time_re = re.compile(r"\[(?P<ts>[^\]]+)\]")
        self._access_log_thread = None
        self._access_log_stop = threading.Event()
        self._update_assets_checked = False

        self.update_fetcher = UpdateFetcher(
            source_url="https://api.github.com/repos/LightningMods/PS4-Store/releases",
            required_files=[
                "homebrew.elf",
                "homebrew.elf.sig",
                "remote.md5",
            ],
            optional_files=[
                "store.prx",
                "store.prx.sig",
            ],
        )
        self.pkg_utils = PkgUtils()
        self.formatter = AutoFormatter()
        self.sorter = AutoSorter()
        self.indexer = AutoIndexer()
        self.planner = WatcherPlanner(self.pkg_utils, self.formatter, self.sorter)
        self.executor = WatcherExecutor(self.pkg_utils, self.formatter, self.sorter)

    def _read_access_log(self) -> None:

        LOG_TAIL_ENABLED = global_envs.WATCHER_ACCESS_LOG_ENABLED
        LOGS_PATH = global_paths.LOGS_DIR_PATH

        if not LOG_TAIL_ENABLED:
            return

        try:
            size = LOGS_PATH.stat().st_size
            if size < self._access_log_offset:
                self._access_log_offset = 0
            with LOGS_PATH.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(self._access_log_offset)
                lines = handle.read().splitlines()
                self._access_log_offset = handle.tell()
            since = self._access_log_since
            for line in lines:
                if line.strip():
                    if since:
                        match = self._access_log_time_re.search(line)
                        if match:
                            try:
                                ts = datetime.strptime(
                                    match.group("ts"), "%d/%b/%Y:%H:%M:%S %z"
                                )
                                if ts.astimezone(timezone.utc) < since:
                                    continue
                            except ValueError:
                                pass
                    log("debug", "Access log", message=line, module="WATCHER")
        except Exception as exc:
            log("warn", "Access log tail failed", message=str(exc), module="WATCHER")

    def _access_log_worker(self) -> None:

        LOG_INTERVAL = global_envs.WATCHER_ACCESS_LOG_INTERVAL

        interval = max(1, LOG_INTERVAL)
        while not self._access_log_stop.is_set():
            self._read_access_log()
            self._access_log_stop.wait(interval)

    def _start_access_log_thread(self) -> None:

        if not self.access_log_enabled:
            return
        if self._access_log_thread and self._access_log_thread.is_alive():
            return
        self._access_log_since = datetime.now(timezone.utc)
        try:
            log_path = Path(self.access_log_path)
            if log_path.exists():
                self._access_log_offset = log_path.stat().st_size
        except Exception:
            self._access_log_offset = 0
        self._access_log_thread = threading.Thread(
            target=self._access_log_worker, daemon=True
        )
        self._access_log_thread.start()

    def _ensure_update_assets(self) -> None:

        try:
            if self._update_assets_checked:
                return
            self._update_assets_checked = True
            cache_dir = Path(os.environ["CACHE_DIR"])
            result = self.update_fetcher.ensure_assets(cache_dir)
            if (result["missing_required"] or result["missing_optional"]) and result[
                "downloaded"
            ]:
                log(
                    "info",
                    "Downloaded update assets",
                    message=", ".join(result["downloaded"]),
                    module="WATCHER",
                )
            if result["unavailable_required"]:
                log(
                    "warn",
                    "Required update assets not found in release",
                    message=", ".join(result["unavailable_required"]),
                    module="WATCHER",
                )
            if result["errors"]:
                log(
                    "warn",
                    "Failed to download update assets",
                    message="; ".join(result["errors"]),
                    module="WATCHER",
                )
        except Exception as exc:
            log("warn", "Update asset check failed", message=str(exc), module="WATCHER")

    def _ensure_store_db_md5(self) -> None:

        try:
            cache_dir = Path(os.environ["CACHE_DIR"])
            md5_path = cache_dir / "store.db.md5"
            json_path = cache_dir / "store.db.json"
            if md5_path.exists() and json_path.exists():
                return
            log(
                "info",
                "Generating store.db checksum files. File is missing",
                module="WATCHER",
            )
            self.indexer.write_store_db_md5()
        except Exception as exc:
            log("warn", "store.db.md5 check failed", message=str(exc), module="WATCHER")

    def start(self):

        if not self.watcher_enabled:
            log("info", "Watcher is disabled. Skipping...", module="WATCHER")
            return
        interval = max(1, self.periodic_scan_seconds)
        log("info", f"Watcher started (interval: {interval}s)", module="WATCHER")
        self._start_access_log_thread()
        next_run = time.monotonic()
        while True:
            now = time.monotonic()
            if now < next_run:
                time.sleep(next_run - now)
            start = time.monotonic()
            try:
                self._ensure_update_assets()
                self._ensure_store_db_md5()
                results, sfo_cache = self.planner.plan()
                if not results:
                    next_run = start + interval
                    continue
                log("info", "Executing planned changes...", module="WATCHER_EXECUTOR")
                batch_size = int(os.environ.get("WATCHER_SCAN_BATCH_SIZE", "50"))
                if batch_size < 1:
                    batch_size = len(results) if results else 1
                batches = [
                    results[i : i + batch_size]
                    for i in range(0, len(results), batch_size)
                ]
                workers = max(1, self.executor_workers)
                workers = min(workers, len(batches))
                stats = {
                    "moves": 0,
                    "renames": 0,
                    "extractions": 0,
                    "errors": 0,
                    "skipped": 0,
                }
                if workers <= 1:
                    _sfo_cache, batch_stats = self.executor.run(
                        results,
                        sfo_cache,
                        log_start=False,
                        log_summary=False,
                        module_name="WATCHER-EXECUTOR-1",
                    )
                    for key in stats:
                        stats[key] += batch_stats.get(key, 0)
                else:
                    worker_batches: list[list[list[dict]]] = [
                        [] for _ in range(workers)
                    ]
                    for idx, batch in enumerate(batches):
                        worker_batches[idx % workers].append(batch)

                    def _run_worker(
                        worker_id: int, batch_groups: list[list[dict]]
                    ) -> dict:
                        worker_stats = {
                            "moves": 0,
                            "renames": 0,
                            "extractions": 0,
                            "errors": 0,
                            "skipped": 0,
                        }
                        module_name = f"WATCHER-EXECUTOR-{worker_id}"
                        for batch in batch_groups:
                            _sfo_cache, batch_stats = self.executor.run(
                                batch,
                                sfo_cache,
                                log_start=False,
                                log_summary=False,
                                module_name=module_name,
                            )
                            for key in worker_stats:
                                worker_stats[key] += batch_stats.get(key, 0)
                        return worker_stats

                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=workers
                    ) as pool:
                        futures = [
                            pool.submit(
                                _run_worker, worker_id + 1, worker_batches[worker_id]
                            )
                            for worker_id in range(workers)
                        ]
                        for future in concurrent.futures.as_completed(futures):
                            worker_stats = future.result()
                            for key in stats:
                                stats[key] += worker_stats.get(key, 0)
                log(
                    "info",
                    f"Planned changes executed: Moves: {stats['moves']}, Renames: {stats['renames']}, "
                    f"Extractions: {stats['extractions']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}",
                    module="WATCHER_EXECUTOR",
                )
                self.indexer.run(results, sfo_cache)
            except Exception as exc:
                log("error", "Watcher cycle failed", message=str(exc), module="WATCHER")
            next_run = start + interval
