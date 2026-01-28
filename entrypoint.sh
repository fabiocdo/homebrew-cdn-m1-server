#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_AUTO_GENERATE_JSON_PERIOD=2
DEFAULT_AUTO_PKG_RENAMER_ENABLED="false"
DEFAULT_AUTO_PKG_RENAMER_TEMPLATE="{title} [{titleid}][{apptype}]"
DEFAULT_AUTO_PKG_RENAMER_MODE="none"
DEFAULT_AUTO_PKG_MOVER_ENABLED="true"
DEFAULT_AUTO_PKG_MOVER_EXCLUDED_DIRS="app"

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
use_default_if_unset AUTO_GENERATE_JSON_PERIOD "$DEFAULT_AUTO_GENERATE_JSON_PERIOD"
use_default_if_unset AUTO_PKG_RENAMER_ENABLED "$DEFAULT_AUTO_PKG_RENAMER_ENABLED"
use_default_if_unset AUTO_PKG_RENAMER_TEMPLATE "$DEFAULT_AUTO_PKG_RENAMER_TEMPLATE"
use_default_if_unset AUTO_PKG_RENAMER_MODE "$DEFAULT_AUTO_PKG_RENAMER_MODE"
use_default_if_unset AUTO_PKG_MOVER_ENABLED "$DEFAULT_AUTO_PKG_MOVER_ENABLED"
use_default_if_unset AUTO_PKG_MOVER_EXCLUDED_DIRS "$DEFAULT_AUTO_PKG_MOVER_EXCLUDED_DIRS"

# CDN PATHs
DATA_DIR="/data"
PKG_DIR="$DATA_DIR/pkg"
MEDIA_DIR="$DATA_DIR/_media"
CACHE_DIR="$DATA_DIR/_cache"

log() {
  printf "%s\n" "$*"
}

clear_console(){
  printf "\033c\n"
}

log_table() {
  printf "    %-28s %s\n" "$1" "$2"
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
log_table "AUTO_GENERATE_JSON_PERIOD" "$(format_value AUTO_GENERATE_JSON_PERIOD "$AUTO_GENERATE_JSON_PERIOD")"
log_table "AUTO_PKG_RENAMER_ENABLED" "$(format_value AUTO_PKG_RENAMER_ENABLED "$AUTO_PKG_RENAMER_ENABLED")"
log_table "AUTO_PKG_RENAMER_TEMPLATE" "$(format_value AUTO_PKG_RENAMER_TEMPLATE "$AUTO_PKG_RENAMER_TEMPLATE")"
log_table "AUTO_PKG_RENAMER_MODE" "$(format_value AUTO_PKG_RENAMER_MODE "$AUTO_PKG_RENAMER_MODE")"
log_table "AUTO_PKG_MOVER_ENABLED" "$(format_value AUTO_PKG_MOVER_ENABLED "$AUTO_PKG_MOVER_ENABLED")"
log_table "AUTO_PKG_MOVER_EXCLUDED_DIRS" "$(format_value AUTO_PKG_MOVER_EXCLUDED_DIRS "$AUTO_PKG_MOVER_EXCLUDED_DIRS")"
log ""

initialize_dir

log ""
exec python3 -u /scripts/watcher.py \
  --base-url "$BASE_URL" \
  --auto-generate-json-period "$AUTO_GENERATE_JSON_PERIOD" \
  --auto-pkg-renamer-enabled "$AUTO_PKG_RENAMER_ENABLED" \
  --auto-pkg-renamer-template "$AUTO_PKG_RENAMER_TEMPLATE" \
  --auto-pkg-renamer-mode "$AUTO_PKG_RENAMER_MODE" \
  --auto-pkg-mover-enabled "$AUTO_PKG_MOVER_ENABLED" \
  --auto-pkg-mover-excluded-dirs "$AUTO_PKG_MOVER_EXCLUDED_DIRS"
