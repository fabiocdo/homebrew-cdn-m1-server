#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

load_env_file_if_unset() {
  file="$1"
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac
    line="${line#export }"
    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf "%s" "$key" | tr -d ' ')"
    [ -z "$key" ] && continue
    value="${value%$'\r'}"
    eval "isset=\${$key+x}"
    if [ -z "$isset" ]; then
      export "$key=$value"
    fi
  done < "$file"
}

load_env_file_if_unset /app/settings.env

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_LOG_LEVEL="info"
DEFAULT_WATCHER_ENABLED="true"
DEFAULT_WATCHER_PERIODIC_SCAN_SECONDS="30"
DEFAULT_WATCHER_ACCESS_LOG_TAIL="true"
DEFAULT_WATCHER_ACCESS_LOG_INTERVAL="5"
DEFAULT_WATCHER_SCAN_BATCH_SIZE="50"
DEFAULT_AUTO_INDEXER_OUTPUT_FORMAT="db,json"
DEFAULT_AUTO_FORMATTER_TEMPLATE="{title}_[{region}]_[{app_type}]_[{version}]"
DEFAULT_AUTO_FORMATTER_MODE="snake_uppercase"
DEFAULT_ENV_VARS=""

# ENVIRONMENT VARIABLES
use_default_if_unset() {
  var="$1"
  default="$2"
  eval "isset=\${$var+x}"
  if [ -z "$isset" ]; then
    eval "$var=\$default"
    DEFAULT_ENV_VARS="${DEFAULT_ENV_VARS}${DEFAULT_ENV_VARS:+,}${var}"
  fi
  export "$var"
}

use_default_if_unset BASE_URL "$DEFAULT_BASE_URL"
use_default_if_unset LOG_LEVEL "$DEFAULT_LOG_LEVEL"
use_default_if_unset WATCHER_ENABLED "$DEFAULT_WATCHER_ENABLED"
use_default_if_unset AUTO_INDEXER_OUTPUT_FORMAT "$DEFAULT_AUTO_INDEXER_OUTPUT_FORMAT"
use_default_if_unset WATCHER_PERIODIC_SCAN_SECONDS "$DEFAULT_WATCHER_PERIODIC_SCAN_SECONDS"
use_default_if_unset WATCHER_ACCESS_LOG_TAIL "$DEFAULT_WATCHER_ACCESS_LOG_TAIL"
use_default_if_unset WATCHER_ACCESS_LOG_INTERVAL "$DEFAULT_WATCHER_ACCESS_LOG_INTERVAL"
use_default_if_unset WATCHER_SCAN_BATCH_SIZE "$DEFAULT_WATCHER_SCAN_BATCH_SIZE"
use_default_if_unset AUTO_FORMATTER_MODE "$DEFAULT_AUTO_FORMATTER_MODE"
use_default_if_unset AUTO_FORMATTER_TEMPLATE "$DEFAULT_AUTO_FORMATTER_TEMPLATE"
export DEFAULT_ENV_VARS

# Normalize boolean-like values
WATCHER_ENABLED=$(printf "%s" "$WATCHER_ENABLED" | tr '[:upper:]' '[:lower:]')
WATCHER_ACCESS_LOG_TAIL=$(printf "%s" "$WATCHER_ACCESS_LOG_TAIL" | tr '[:upper:]' '[:lower:]')

# PATHs
DATA_DIR="/data"
PKG_DIR="${DATA_DIR}/pkg"
GAME_DIR="${PKG_DIR}/game"
DLC_DIR="${PKG_DIR}/dlc"
UPDATE_DIR="${PKG_DIR}/update"
SAVE_DIR="${PKG_DIR}/save"
UNKNOWN_DIR="${PKG_DIR}/_unknown"
MEDIA_DIR="${PKG_DIR}/_media"
CACHE_DIR="${DATA_DIR}/_cache"
ERROR_DIR="${DATA_DIR}/_error"
LOG_DIR="${DATA_DIR}/_logs"
STORE_DIR="${DATA_DIR}"
INDEX_DIR="${DATA_DIR}"
STORE_DB_PATH="${DATA_DIR}/store.db"

log() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

create_path() {
  target="$1"
  label="$2"
  root="$3"
  if [ ! -d "$target" ]; then
    mkdir -p "$target"
    if [ -n "$label" ] && [ -n "$root" ]; then
      log "Initialized ${label} directory at ${root}"
    else
      log "Initialized directory at $target"
    fi
    initialized_any="true"
  fi
}

initialize_data_dir(){
  log "Initializing directories and files..."
  initialized_any="false"
  create_path "$GAME_DIR" "game/" "$PKG_DIR/"
  create_path "$DLC_DIR" "dlc/" "$PKG_DIR/"
  create_path "$UPDATE_DIR" "update/" "$PKG_DIR/"
  create_path "$SAVE_DIR" "save/" "$PKG_DIR/"
  create_path "$UNKNOWN_DIR" "_unknown/" "$PKG_DIR/"
  create_path "$MEDIA_DIR" "_media/" "$PKG_DIR/"
  create_path "$CACHE_DIR" "_cache/" "$DATA_DIR/"
  create_path "$ERROR_DIR" "_error/" "$DATA_DIR/"
  create_path "$LOG_DIR" "_logs/" "$DATA_DIR/"
  marker_path="$PKG_DIR/_PUT_YOUR_PKGS_HERE"
  if [ ! -f "$marker_path" ]; then
    printf "%s\n" "Place PKG files in this directory or its subfolders." > "$marker_path"
    log "Initialized _PUT_YOUR_PKGS_HERE marker at $PKG_DIR/"
    initialized_any="true"
  fi
  if [ "$initialized_any" != "true" ]; then
    log "Great! Nothing to initialize!"
  fi
}

initialize_store_db() {
  if ! command -v sqlite3 >/dev/null 2>&1; then
    log "sqlite3 not found; skipping store.db initialization."
    return
  fi
  if [ ! -f "$STORE_DB_PATH" ]; then
    log "Initializing store.db at $STORE_DB_PATH"
  fi
  sqlite3 "$STORE_DB_PATH" <<'SQL'
CREATE TABLE IF NOT EXISTS homebrews (
  "pid" INTEGER,
  "id" TEXT,
  "name" TEXT,
  "desc" TEXT,
  "image" TEXT,
  "package" TEXT,
  "version" TEXT,
  "picpath" TEXT,
  "desc_1" TEXT,
  "desc_2" TEXT,
  "ReviewStars" REAL,
  "Size" INTEGER,
  "Author" TEXT,
  "apptype" TEXT,
  "pv" TEXT,
  "main_icon_path" TEXT,
  "main_menu_pic" TEXT,
  "releaseddate" TEXT,
  "number_of_downloads" TEXT,
  "github" TEXT,
  "video" TEXT,
  "twitter" TEXT,
  "md5" TEXT
);
SQL
}

hostport="${BASE_URL#*://}"
hostport="${hostport%%/*}"
host="${hostport%%:*}"
port="${hostport##*:}"
if [ "$host" = "$hostport" ]; then
  port="80"
fi

initialize_data_dir

log "Starting NGINX..."
nginx
log "NGINX is running on ${host}:${port}"
log ""

initialize_store_db

if [ "$WATCHER_ENABLED" = "true" ]; then
  exec python3 -u -m src
fi
log "Watcher is disabled."
exec tail -f /dev/null
