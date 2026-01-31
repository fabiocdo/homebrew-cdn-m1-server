import argparse
import hashlib
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import settings
from modules.auto_indexer import ensure_icon, run as run_indexer
from modules.auto_mover import apply as apply_mover
from modules.auto_mover import dry_run as mover_dry_run
from modules.auto_renamer import apply as apply_renamer
from modules.auto_renamer import dry_run as renamer_dry_run
from utils.pkg_utils import scan_pkgs
from utils.log_utils import clear_worker_label, log, set_worker_label


def parse_settings():
    """Parse CLI args into settings."""
    parser = argparse.ArgumentParser()
    for flag, opts in settings.CLI_ARGS:
        parser.add_argument(flag, **opts)
    args = parser.parse_args()

    def parse_bool(value):
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    settings.BASE_URL = args.base_url
    settings.LOG_LEVEL = args.log_level
    settings.PKG_WATCHER_ENABLED = parse_bool(args.pkg_watcher_enabled)
    settings.AUTO_RENAMER_ENABLED = parse_bool(args.auto_renamer_enabled)
    settings.AUTO_RENAMER_TEMPLATE = args.auto_renamer_template
    settings.AUTO_RENAMER_MODE = args.auto_renamer_mode.lower()
    settings.AUTO_RENAMER_EXCLUDED_DIRS = args.auto_renamer_excluded_dirs
    settings.AUTO_MOVER_ENABLED = parse_bool(args.auto_mover_enabled)
    settings.AUTO_MOVER_EXCLUDED_DIRS = args.auto_mover_excluded_dirs
    settings.AUTO_INDEXER_ENABLED = parse_bool(args.auto_indexer_enabled)
    settings.INDEX_JSON_ENABLED = parse_bool(args.index_json_enabled)
    settings.PROCESS_WORKERS = args.process_workers


def watch(on_change):
    """Watch pkg directory and trigger rename/move/index updates."""
    if shutil.which("inotifywait") is None:
        log("error", "inotifywait not found; skipping watcher.")
        return
    if not settings.PKG_DIR.exists():
        return

    log("info", f"Starting watcher on {settings.PKG_DIR}")
    cmd = [
        "inotifywait",
        "-q",
        "-m",
        "-r",
        "-e",
        "delete",
        "-e",
        "close_write",
        "-e",
        "moved_from",
        "-e",
        "moved_to",
        "--format",
        "%w%f|%e",
        str(settings.PKG_DIR),
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if process.stdout is None:
        return

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            log("debug", f"Watcher output: {line}", module="WATCHER")
            continue
        path, events = line.split("|", 1)
        log("debug", f"Captured events: {events} on {path}", module="WATCHER")
        on_change([(path, events)])


def start():
    """Entry point for the indexer watcher."""
    parse_settings()
    last_moved_to = {}
    last_moved_from = {}
    module_touched_at = {}
    module_suppression_seconds = 5.0
    move_event_suppression_seconds = 10.0

    def run_automations(events=None):
        initial_run = events is None
        manual_events = []
        candidate_paths = []
        should_reindex = initial_run
        if not initial_run:
            for path, event_str in events:
                manual_events.append((path, event_str))

            if not manual_events:
                return

        if not settings.PKG_WATCHER_ENABLED:
            return

        if manual_events:
            allowed_exts = {".pkg"}
            relevant_events = []
            moved_to_paths = set()
            now = time.monotonic()
            for path, event_str in manual_events:
                if not path.lower().endswith(tuple(allowed_exts)):
                    continue
                touched_at = module_touched_at.get(path)
                if touched_at is not None and (now - touched_at) < module_suppression_seconds:
                    continue
                events = {item.strip() for item in event_str.split(",") if item.strip()}
                if "CREATE" in events:
                    continue
                if "MOVED_FROM" in events:
                    last_moved_from[path] = time.monotonic()
                if "MOVED_TO" in events:
                    moved_to_paths.add(path)
                    last_moved_to[path] = time.monotonic()
                relevant_events.append((path, event_str))

            if not relevant_events:
                return

            filtered_events = []
            for path, event_str in relevant_events:
                events = {item.strip() for item in event_str.split(",") if item.strip()}
                if "CLOSE_WRITE" in events and path in moved_to_paths:
                    continue
                if "CLOSE_WRITE" in events:
                    last_moved = last_moved_to.get(path)
                    if (
                        last_moved is not None
                        and (time.monotonic() - last_moved) < move_event_suppression_seconds
                    ):
                        continue
                if "MOVED_FROM" in events:
                    last_moved = last_moved_to.get(path)
                    if (
                        last_moved is not None
                        and (time.monotonic() - last_moved) < move_event_suppression_seconds
                    ):
                        continue
                filtered_events.append((path, event_str))

            if not filtered_events:
                return
            manual_events = filtered_events

            candidate_set = set()
            for path, event_str in manual_events:
                events = {item.strip() for item in event_str.split(",") if item.strip()}
                path_obj = Path(path)
                if "DELETE" in events or "MOVED_FROM" in events:
                    should_reindex = True
                    continue
                if not path_obj.exists():
                    should_reindex = True
                    continue
                candidate_set.add(path_obj)
                should_reindex = True
            candidate_paths = list(candidate_set)

        if initial_run:
            pkgs = list(scan_pkgs()) if settings.PKG_DIR.exists() else []
        else:
            pkgs = list(scan_pkgs(paths=candidate_paths)) if candidate_paths else []

        def process_pkg(pkg, data):
            current_pkg = pkg
            blocked_sources = set()
            touched = []

            if settings.AUTO_RENAMER_ENABLED:
                renamer_dry = renamer_dry_run([(current_pkg, data)])
                blocked_sources.update(renamer_dry.get("blocked_sources", []))
                renamer_result = apply_renamer(renamer_dry)
                touched.extend(renamer_result.get("touched_paths", []))

                renamed = renamer_result.get("renamed", [])
                if renamed:
                    current_pkg = renamed[0][1]

                if str(pkg) in blocked_sources:
                    return touched

            if settings.AUTO_MOVER_ENABLED:
                mover_dry = mover_dry_run([(current_pkg, data)], skip_paths=blocked_sources)
                mover_result = apply_mover(mover_dry)
                touched.extend(mover_result.get("touched_paths", []))
                moved = mover_result.get("moved", [])
                if moved:
                    current_pkg = moved[0][1]

            ensure_icon(current_pkg, data)
            return touched

        touched_paths = []
        now = time.monotonic()
        worker_count = 1
        try:
            worker_count = max(1, int(settings.PROCESS_WORKERS))
        except Exception:
            worker_count = max(1, os.cpu_count() or 1)

        def process_batch(items, label=None):
            batch_touched = []
            if label is not None:
                set_worker_label(label)
            for pkg, data in items:
                batch_touched.append(process_pkg(pkg, data))
            if label is not None:
                clear_worker_label()
            return batch_touched

        if worker_count <= 1 or len(pkgs) <= 1:
            for pkg, data in pkgs:
                touched_paths.extend(process_pkg(pkg, data))
        else:
            shards = [[] for _ in range(worker_count)]
            for pkg, data in pkgs:
                digest = hashlib.md5(str(pkg).encode("utf-8")).hexdigest()
                shard = int(digest, 16) % worker_count
                shards[shard].append((pkg, data))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = []
                for idx, shard_pkgs in enumerate(shards, start=1):
                    if not shard_pkgs:
                        continue
                    futures.append(executor.submit(process_batch, shard_pkgs, str(idx)))
                for future in as_completed(futures):
                    for touched in future.result():
                        touched_paths.extend(touched)

        for path in touched_paths:
            module_touched_at[path] = now
        if settings.AUTO_INDEXER_ENABLED and should_reindex:
            pkgs = list(scan_pkgs(use_cache=True)) if settings.PKG_DIR.exists() else []
            run_indexer(pkgs)


        if not initial_run:
            return

    run_automations()
    watch(run_automations)


if __name__ == "__main__":
    start()
