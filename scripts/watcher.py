import argparse
import shutil
import subprocess
import threading

import settings
from auto_indexer import run as run_indexer
from auto_mover import run as run_mover
from auto_renamer import run as run_renamer
from utils.pkg_utils import scan_pkgs
from utils.log_utils import log


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
    settings.PKG_WATCHER_ENABLED = parse_bool(args.pkg_watcher_enabled)
    settings.AUTO_INDEXER_DEBOUNCE_TIME_SECONDS = (
        args.auto_indexer_debounce_time_seconds
    )
    settings.AUTO_RENAMER_ENABLED = parse_bool(args.auto_renamer_enabled)
    settings.AUTO_RENAMER_TEMPLATE = args.auto_renamer_template
    settings.AUTO_RENAMER_MODE = args.auto_renamer_mode
    settings.AUTO_MOVER_ENABLED = parse_bool(args.auto_mover_enabled)
    settings.AUTO_MOVER_EXCLUDED_DIRS = args.auto_mover_excluded_dirs
    settings.AUTO_INDEXER_ENABLED = parse_bool(args.auto_indexer_enabled)


def watch(on_change):
    """Watch pkg directory and trigger rename/move/index updates."""
    if shutil.which("inotifywait") is None:
        log("error", "inotifywait not found; skipping watcher.")
        return
    if not settings.PKG_DIR.exists():
        return

    log("info", f"Starting watcher on {settings.PKG_DIR}")
    last_moved_from = ""

    cmd = [
        "inotifywait",
        "-q",
        "-m",
        "-r",
        "-e",
        "create",
        "-e",
        "delete",
        "-e",
        "move",
        "-e",
        "close_write",
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
            log("info", line)
            continue
        path, events = line.split("|", 1)
        if "MOVED_FROM" in events:
            last_moved_from = path
            continue
        if "MOVED_TO" in events:
            if last_moved_from:
                log("modified", f"Moved: {last_moved_from} -> {path}")
                last_moved_from = ""
            else:
                log("modified", f"Moved: {path}")
            on_change(schedule_index=True)
            continue
        if "CREATE" in events or "DELETE" in events:
            if "DELETE" in events:
                log("deleted", f"Change detected: {events} {path}")
            else:
                log("created", f"Change detected: {events} {path}")
            on_change(schedule_index=True)
            continue
        log("modified", f"Change detected: {events} {path}")
        on_change(schedule_index=True)


def start():
    """Entry point for the indexer watcher."""
    parse_settings()
    if not settings.PKG_WATCHER_ENABLED:
        log("info", "Automation watcher disabled.")
        return
    debounce_timer = None

    def schedule_generate(pkgs):
        nonlocal debounce_timer
        if not settings.AUTO_INDEXER_ENABLED:
            return
        if debounce_timer and debounce_timer.is_alive():
            debounce_timer.cancel()

        def run():
            nonlocal debounce_timer
            debounce_timer = None
            run_indexer(pkgs)

        debounce_timer = threading.Timer(
            settings.AUTO_INDEXER_DEBOUNCE_TIME_SECONDS,
            run,
        )
        debounce_timer.daemon = True
        debounce_timer.start()

    def run_automations(schedule_index):
        if not settings.PKG_WATCHER_ENABLED:
            return
        pkgs = list(scan_pkgs()) if settings.PKG_DIR.exists() else []
        if settings.AUTO_RENAMER_ENABLED:
            run_renamer(pkgs)
        if settings.AUTO_MOVER_ENABLED:
            run_mover(pkgs)
        if settings.AUTO_RENAMER_ENABLED or settings.AUTO_MOVER_ENABLED:
            pkgs = list(scan_pkgs()) if settings.PKG_DIR.exists() else []
        if schedule_index:
            schedule_generate(pkgs)
        elif settings.AUTO_INDEXER_ENABLED:
            run_indexer(pkgs)

    run_automations(schedule_index=False)
    watch(run_automations)


if __name__ == "__main__":
    start()
