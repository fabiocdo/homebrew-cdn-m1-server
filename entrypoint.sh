#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_PKG_WATCHER_ENABLED="true"
DEFAULT_AUTO_INDEXER_ENABLED="true"
DEFAULT_AUTO_INDEXER_DEBOUNCE_TIME_SECONDS=3
DEFAULT_AUTO_RENAMER_ENABLED="false"
DEFAULT_AUTO_RENAMER_TEMPLATE="{title} [{titleid}][{apptype}]"
DEFAULT_AUTO_RENAMER_MODE="none"
DEFAULT_AUTO_MOVER_ENABLED="true"
DEFAULT_AUTO_MOVER_EXCLUDED_DIRS="app"

# ENVIRONMENT VARIABLES
use_default_if_unset() {
  var="$1"
  eval "isset=\${$var+x}"
  if [ -z "$isset" ]; then
    eval "$var=\$2"
    eval "${var}_IS_DEFAULT=true"
  fi
}

use_default_if_unset BASE_URL "$DEFAULT_BASE_URL"
use_default_if_unset PKG_WATCHER_ENABLED "$DEFAULT_PKG_WATCHER_ENABLED"
use_default_if_unset AUTO_INDEXER_ENABLED "$DEFAULT_AUTO_INDEXER_ENABLED"
use_default_if_unset AUTO_INDEXER_DEBOUNCE_TIME_SECONDS "$DEFAULT_AUTO_INDEXER_DEBOUNCE_TIME_SECONDS"
use_default_if_unset AUTO_RENAMER_ENABLED "$DEFAULT_AUTO_RENAMER_ENABLED"
use_default_if_unset AUTO_RENAMER_TEMPLATE "$DEFAULT_AUTO_RENAMER_TEMPLATE"
use_default_if_unset AUTO_RENAMER_MODE "$DEFAULT_AUTO_RENAMER_MODE"
use_default_if_unset AUTO_MOVER_ENABLED "$DEFAULT_AUTO_MOVER_ENABLED"
use_default_if_unset AUTO_MOVER_EXCLUDED_DIRS "$DEFAULT_AUTO_MOVER_EXCLUDED_DIRS"

# CDN PATHs
DATA_DIR="/data"
PKG_DIR="$DATA_DIR/pkg"
MEDIA_DIR="$DATA_DIR/_media"
CACHE_DIR="$DATA_DIR/_cache"

log() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

clear_console(){
  printf "\033c\n"
}

log_table() {
  printf "%s     %-38s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2"
}

format_value() {
  var="$1"
  value="$2"
  is_default=""
  eval "is_default=\${${var}_IS_DEFAULT-}"
  if [ "$is_default" = "true" ]; then
    printf "%s %b(DEFAULT)%b" "$value" "\033[0;90m" "\033[0m"
  else
    printf "%s" "$value"
  fi
}

initialize_dir(){
  log "[·] Initializing directories and files..."
  initialized_any="false"
  create_path "$PKG_DIR/game" "game/" "$PKG_DIR/"
  create_path "$PKG_DIR/dlc" "dlc/" "$PKG_DIR/"
  create_path "$PKG_DIR/update" "update/" "$PKG_DIR/"
  create_path "$PKG_DIR/app" "app/" "$PKG_DIR/"
  create_path "$MEDIA_DIR" "_media/" "$DATA_DIR/"
  create_path "$CACHE_DIR" "_cache/" "$DATA_DIR/"
  marker_path="$PKG_DIR/_PUT_YOUR_PKGS_HERE"
  if [ ! -f "$marker_path" ]; then
    printf "%s\n" "Place PKG files in this directory or its subfolders." > "$marker_path"
    log "[·] Initialized _PUT_YOUR_PKGS_HERE marker at $PKG_DIR/"
    initialized_any="true"
  fi
  if [ "$initialized_any" != "true" ]; then
    log "[·] Great! Nothing to initialize!"
  fi
}

create_path() {
  target="$1"
  label="$2"
  root="$3"
  if [ ! -d "$target" ]; then
    mkdir -p "$target"
    if [ -n "$label" ] && [ -n "$root" ]; then
      log "[·] Initialized ${label} directory at ${root}"
    else
      log "[·] Initialized directory at $target"
    fi
    initialized_any="true"
  fi
}

hostport="${BASE_URL#*://}"
hostport="${hostport%%/*}"
host="${hostport%%:*}"
port="${hostport##*:}"
if [ "$host" = "$hostport" ]; then
  port="80"
fi

clear_console
log "[·] Starting NGINX..."
nginx
log "[·] NGINX is running on ${host}:${port}"

log ""
log "[·] Starting Auto Indexer with settings:"
log_table "SERVER URL" "$(format_value BASE_URL "$BASE_URL")"
log_table "PKG_WATCHER_ENABLED" "$(format_value PKG_WATCHER_ENABLED "$PKG_WATCHER_ENABLED")"
log_table "AUTO_INDEXER_ENABLED" "$(format_value AUTO_INDEXER_ENABLED "$AUTO_INDEXER_ENABLED")"
log_table "AUTO_INDEXER_DEBOUNCE_TIME_SECONDS" "$(format_value AUTO_INDEXER_DEBOUNCE_TIME_SECONDS "$AUTO_INDEXER_DEBOUNCE_TIME_SECONDS")"
log_table "AUTO_RENAMER_ENABLED" "$(format_value AUTO_RENAMER_ENABLED "$AUTO_RENAMER_ENABLED")"
log_table "AUTO_RENAMER_TEMPLATE" "$(format_value AUTO_RENAMER_TEMPLATE "$AUTO_RENAMER_TEMPLATE")"
log_table "AUTO_RENAMER_MODE" "$(format_value AUTO_RENAMER_MODE "$AUTO_RENAMER_MODE")"
log_table "AUTO_MOVER_ENABLED" "$(format_value AUTO_MOVER_ENABLED "$AUTO_MOVER_ENABLED")"
log_table "AUTO_MOVER_EXCLUDED_DIRS" "$(format_value AUTO_MOVER_EXCLUDED_DIRS "$AUTO_MOVER_EXCLUDED_DIRS")"
log ""

initialize_dir

log ""
if [ "$PKG_WATCHER_ENABLED" = "true" ]; then
  exec python3 -u /scripts/watcher.py \
    --base-url "$BASE_URL" \
    --pkg-watcher-enabled "$PKG_WATCHER_ENABLED" \
    --auto-indexer-enabled "$AUTO_INDEXER_ENABLED" \
    --auto-indexer-debounce-time-seconds "$AUTO_INDEXER_DEBOUNCE_TIME_SECONDS" \
    --auto-renamer-enabled "$AUTO_RENAMER_ENABLED" \
    --auto-renamer-template "$AUTO_RENAMER_TEMPLATE" \
    --auto-renamer-mode "$AUTO_RENAMER_MODE" \
    --auto-mover-enabled "$AUTO_MOVER_ENABLED" \
    --auto-mover-excluded-dirs "$AUTO_MOVER_EXCLUDED_DIRS"
fi
log "[·] PKG watcher is disabled."
exec tail -f /dev/null
