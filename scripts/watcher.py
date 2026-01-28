import argparse
import shutil
import subprocess
import threading

import settings
from auto_indexer import build_index
from auto_mover import run as run_mover
from auto_renamer import run as run_renamer
from utils.pkg_utils import scan_pkgs
from utils.log_utils import log


def parse_config():
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
    settings.AUTO_GENERATE_JSON_PERIOD = args.auto_generate_json_period
    settings.AUTO_PKG_RENAMER_ENABLED = parse_bool(args.auto_pkg_renamer_enabled)
    settings.AUTO_PKG_RENAMER_TEMPLATE = args.auto_pkg_renamer_template
    settings.AUTO_PKG_RENAMER_MODE = args.auto_pkg_renamer_mode
    settings.AUTO_PKG_MOVER_ENABLED = parse_bool(args.auto_pkg_mover_enabled)
    settings.AUTO_PKG_MOVER_EXCLUDED_DIRS = args.auto_pkg_mover_excluded_dirs


def watch_pkg_dir(auto_generate_json_period):
    """Watch pkg directory and trigger rename/move/index updates."""
    if shutil.which("inotifywait") is None:
        log("error", "inotifywait not found; skipping watcher.")
        return
    if not settings.PKG_DIR.exists():
        return

    last_moved_from = ""
    debounce_timer = None

    def schedule_generate(pkgs):
        nonlocal debounce_timer
        if debounce_timer and debounce_timer.is_alive():
            debounce_timer.cancel()

        def run():
            nonlocal debounce_timer
            debounce_timer = None
            build_index(pkgs)

        debounce_timer = threading.Timer(auto_generate_json_period, run)
        debounce_timer.daemon = True
        debounce_timer.start()

    def handle_change():
        pkgs = list(scan_pkgs())
        if settings.AUTO_PKG_RENAMER_ENABLED:
            run_renamer(pkgs)
        if settings.AUTO_PKG_MOVER_ENABLED:
            run_mover(pkgs)
        if settings.AUTO_PKG_RENAMER_ENABLED or settings.AUTO_PKG_MOVER_ENABLED:
            pkgs = list(scan_pkgs())
        schedule_generate(pkgs)

    cmd = [
        "inotifywait",
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
            handle_change()
            continue
        if "CREATE" in events or "DELETE" in events:
            if "DELETE" in events:
                log("deleted", f"Change detected: {events} {path}")
            else:
                log("created", f"Change detected: {events} {path}")
            handle_change()
            continue
        log("modified", f"Change detected: {events} {path}")
        handle_change()

def main():
    """Entry point for the indexer watcher."""
    parse_config()
    pkgs = []
    if settings.PKG_DIR.exists():
        pkgs = list(scan_pkgs())
    if settings.AUTO_PKG_RENAMER_ENABLED:
        run_renamer(pkgs)
    if settings.AUTO_PKG_MOVER_ENABLED:
        run_mover(pkgs)
    if settings.AUTO_PKG_RENAMER_ENABLED or settings.AUTO_PKG_MOVER_ENABLED:
        pkgs = list(scan_pkgs())
    build_index(pkgs)
    watch_pkg_dir(settings.AUTO_GENERATE_JSON_PERIOD)


if __name__ == "__main__":
    main()
