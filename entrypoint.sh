#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_AUTO_GENERATE_JSON_PERIOD=2
DEFAULT_AUTO_RENAME_PKGS="false"
DEFAULT_AUTO_RENAME_TEMPLATE="{title} [{titleid}][{apptype}]"
DEFAULT_AUTO_RENAME_TITLE_MODE="none"
GRAY="$(printf '\033[0;90m')"
RESET="$(printf '\033[0m')"

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
use_default_if_unset AUTO_RENAME_PKGS "$DEFAULT_AUTO_RENAME_PKGS"
use_default_if_unset AUTO_RENAME_TEMPLATE "$DEFAULT_AUTO_RENAME_TEMPLATE"
use_default_if_unset AUTO_RENAME_TITLE_MODE "$DEFAULT_AUTO_RENAME_TITLE_MODE"

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
    printf "%s %s(DEFAULT)%s" "$value" "$GRAY" "$RESET"
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
log_table "AUTO_RENAME_PKGS" "$(format_value AUTO_RENAME_PKGS "$AUTO_RENAME_PKGS")"
log_table "AUTO_RENAME_TEMPLATE" "$(format_value AUTO_RENAME_TEMPLATE "$AUTO_RENAME_TEMPLATE")"
log_table "AUTO_RENAME_TITLE_MODE" "$(format_value AUTO_RENAME_TITLE_MODE "$AUTO_RENAME_TITLE_MODE")"
log ""

initialize_dir

log ""
exec python3 -u /scripts/auto_indexer.py \
  --base-url "$BASE_URL" \
  --auto-generate-json-period "$AUTO_GENERATE_JSON_PERIOD" \
  --auto-rename-pkgs "$AUTO_RENAME_PKGS" \
  --auto-rename-template "$AUTO_RENAME_TEMPLATE" \
  --auto-rename-title-mode "$AUTO_RENAME_TITLE_MODE"
