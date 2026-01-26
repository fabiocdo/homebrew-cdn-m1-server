#!/bin/sh
set -e

PKG_DIR="/data/pkg"
MEDIA_DIR="/data/_media"
CACHE_DIR="/data/_cache"
GENERATE_JSON_PERIOD="${GENERATE_JSON_PERIOD:-5}"
GREEN="\033[0;32m"
RESET="\033[0m"

generate() {
  echo "[+] Generating index.json..."
  mkdir -p "$PKG_DIR" "$MEDIA_DIR" "$CACHE_DIR"
  RUN_MODE=watch python3 /generate-index.py
}

move_only() {
  RUN_MODE=move python3 /generate-index.py
}

# Initial generation
mkdir -p "$PKG_DIR" "$MEDIA_DIR" "$CACHE_DIR"
RUN_MODE=init python3 /generate-index.py

# Automatic watcher
if [ -d "$PKG_DIR" ]; then
  last_moved_from=""
  debounce_pid=""

  schedule_generate() {
    if [ -n "$debounce_pid" ] && kill -0 "$debounce_pid" 2>/dev/null; then
      kill "$debounce_pid" 2>/dev/null || true
      wait "$debounce_pid" 2>/dev/null || true
    fi
    (
      sleep "$GENERATE_JSON_PERIOD"
      debounce_pid=""
      generate
    ) &
    debounce_pid="$!"
  }

  inotifywait -m -r -e create -e delete -e move -e close_write --format "%w%f|%e" "$PKG_DIR" | while IFS="|" read -r path events; do
    case "$events" in
      *MOVED_FROM*)
        last_moved_from="$path"
        ;;
      *MOVED_TO*)
        if [ -n "$last_moved_from" ]; then
          printf "${GREEN}[*] Moved: %s -> %s${RESET}\n" "$last_moved_from" "$path"
          last_moved_from=""
        else
          printf "${GREEN}[*] Moved: %s${RESET}\n" "$path"
        fi
        move_only
        schedule_generate
        ;;
      *CREATE*|*DELETE*)
        printf "${GREEN}[*] Change detected: %s %s${RESET}\n" "$events" "$path"
        move_only
        schedule_generate
        ;;
      *)
        printf "${GREEN}[*] Change detected: %s %s${RESET}\n" "$events" "$path"
        move_only
        schedule_generate
        ;;
    esac
  done &
fi


printf "${GREEN}[+] Starting NGINX...${RESET}\n"
exec nginx -g "daemon off;"
