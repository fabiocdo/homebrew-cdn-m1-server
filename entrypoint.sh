#!/bin/sh
set -e

PKG_DIR="/data/pkg"
MEDIA_DIR="/data/_media"
CACHE_DIR="/data/_cache"
AUTO_GENERATE_JSON_PERIOD="${AUTO_GENERATE_JSON_PERIOD:-2}"
GREEN="$(printf '\033[0;32m')"
YELLOW="$(printf '\033[0;33m')"
RED="$(printf '\033[0;31m')"
PINK="$(printf '\033[1;95m')"
RESET="$(printf '\033[0m')"

log() {
  action="$1"
  shift
  case "$action" in
    created)
      color="$GREEN"
      prefix="[+]"
      ;;
    modified)
      color="$YELLOW"
      prefix="[*]"
      ;;
    deleted)
      color="$RED"
      prefix="[-]"
      ;;
    error)
      color="$PINK"
      prefix="[!]"
      ;;
    info)
      color="$RESET"
      prefix="[·]"
      ;;
    *)
      color="$RESET"
      prefix="[*]"
      ;;
  esac
  printf "%s%s %s%s\n" "$color" "$prefix" "$*" "$RESET"
}

generate() {
  log info "Generating index.json..."
  mkdir -p "$PKG_DIR" "$MEDIA_DIR" "$CACHE_DIR"
  RUN_MODE=watch python3 /generate-index.py
}

move_only() {
  RUN_MODE=move python3 /generate-index.py
  return $?
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
      sleep "$AUTO_GENERATE_JSON_PERIOD"
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
          log modified "Moved: $last_moved_from -> $path"
          last_moved_from=""
        else
          log modified "Moved: $path"
        fi
        if move_only; then
          schedule_generate
        fi
        ;;
      *CREATE*|*DELETE*)
        if echo "$events" | grep -q "DELETE"; then
          log deleted "Change detected: $events $path"
        else
          log created "Change detected: $events $path"
        fi
        if move_only; then
          schedule_generate
        fi
        ;;
      *)
        log modified "Change detected: $events $path"
        if move_only; then
          schedule_generate
        fi
        ;;
    esac
  done &
fi


log info "Starting NGINX..."
exec nginx -g "daemon off;"
