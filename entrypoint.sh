#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

if [ -f /app/settings.env ]; then
  set -a
  . /app/settings.env
  set +a
fi

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_LOG_LEVEL="info"
DEFAULT_PKG_WATCHER_ENABLED="true"
DEFAULT_AUTO_INDEXER_ENABLED="true"
DEFAULT_INDEX_JSON_ENABLED="false"
DEFAULT_AUTO_FORMATTER_ENABLED="true"
DEFAULT_AUTO_FORMATTER_TEMPLATE="{title} {title_id} {app_type}"
DEFAULT_AUTO_FORMATTER_MODE="none"
DEFAULT_AUTO_SORTER_ENABLED="true"
DEFAULT_PERIODIC_SCAN_SECONDS="30"

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
use_default_if_unset LOG_LEVEL "$DEFAULT_LOG_LEVEL"
use_default_if_unset PKG_WATCHER_ENABLED "$DEFAULT_PKG_WATCHER_ENABLED"
use_default_if_unset AUTO_INDEXER_ENABLED "$DEFAULT_AUTO_INDEXER_ENABLED"
use_default_if_unset INDEX_JSON_ENABLED "$DEFAULT_INDEX_JSON_ENABLED"
use_default_if_unset AUTO_FORMATTER_ENABLED "$DEFAULT_AUTO_FORMATTER_ENABLED"
use_default_if_unset AUTO_SORTER_ENABLED "$DEFAULT_AUTO_SORTER_ENABLED"
use_default_if_unset PERIODIC_SCAN_SECONDS "$DEFAULT_PERIODIC_SCAN_SECONDS"
use_default_if_unset AUTO_FORMATTER_MODE "$DEFAULT_AUTO_FORMATTER_MODE"
use_default_if_unset AUTO_FORMATTER_TEMPLATE "$DEFAULT_AUTO_FORMATTER_TEMPLATE"
use_default_if_unset DATA_DIR "/data"

# PATHs
DATA_DIR="${DATA_DIR:-/data}"
PKG_DIR="${DATA_DIR}/pkg"
GAME_DIR="${PKG_DIR}/game"
DLC_DIR="${PKG_DIR}/dlc"
UPDATE_DIR="${PKG_DIR}/update"
SAVE_DIR="${PKG_DIR}/save"
UNKNOWN_DIR="${PKG_DIR}/_unknown"
MEDIA_DIR="${DATA_DIR}/_media"
CACHE_DIR="${DATA_DIR}/_cache"
ERROR_DIR="${DATA_DIR}/_error"
STORE_DIR="${DATA_DIR}"
INDEX_DIR="${DATA_DIR}"
STORE_DB_PATH="${DATA_DIR}/store.db"

log() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

COLOR_GREEN="\033[0;92m"
COLOR_BLUE="\033[1;94m"
COLOR_YELLOW="\033[1;93m"

clear_console(){
  printf "\033c\n"
}

format_value() {
  var="$1"
  value="$2"
  is_default=""
  eval "is_default=\${${var}_IS_DEFAULT-}"
  value="$(printf "%s" "$value" | tr '[:lower:]' '[:upper:]')"
  if [ "$is_default" = "true" ]; then
    printf "%s %b(DEFAULT)%b" "$value" "\033[0;90m" "\033[0m"
  else
    printf "%s" "$value"
  fi
}

color_value() {
  value="$1"
  color="$2"
  printf "%b%s%b" "$color" "$value" "\033[0m"
}

strip_ansi() {
  printf "%s" "$1" | sed 's/\x1B\[[0-9;]*m//g'
}

format_kv_plain() {
  key="$1"
  value="$2"
  key_pad=$((BOX_KEY_WIDTH - ${#key}))
  if [ "$key_pad" -lt 1 ]; then
    key_pad=1
  fi
  printf "%s%*s%s\n" "$key" "$key_pad" "" "$value"
}

format_kv_colored() {
  key_plain="$1"
  key_display="$2"
  value_display="$3"
  key_pad=$((BOX_KEY_WIDTH - ${#key_plain}))
  if [ "$key_pad" -lt 1 ]; then
    key_pad=1
  fi
  printf "%s%*s%s\n" "$key_display" "$key_pad" "" "$value_display"
}

box_border() {
  printf "%s\n" "$(printf "%*s" "$BOX_WIDTH" "" | tr ' ' '=')"
}

box_line() {
  content="$1"
  plain="$(strip_ansi "$content")"
  pad=$((BOX_WIDTH - 6 - ${#plain}))
  if [ "$pad" -lt 0 ]; then
    pad=0
  fi
  printf "|| %s%*s ||\n" "$content" "$pad" ""
}

build_content_lines_plain() {
  printf "%s\n" "HOMEBREW-STORE-CDN"
  printf "\n"
  format_kv_plain "BASE_URL" "$(format_value BASE_URL "$BASE_URL")"
  format_kv_plain "LOG_LEVEL" "$(format_value LOG_LEVEL "$LOG_LEVEL")"
  format_kv_plain "DATA_DIR" "$(format_value DATA_DIR "$DATA_DIR")"
  printf "\n"
  format_kv_plain "PKG_WATCHER_ENABLED" "$(format_value PKG_WATCHER_ENABLED "$PKG_WATCHER_ENABLED")"
  printf "\n"
  format_kv_plain "AUTO_INDEXER_ENABLED" "$(format_value AUTO_INDEXER_ENABLED "$AUTO_INDEXER_ENABLED")"
  format_kv_plain "INDEX_JSON_ENABLED" "$(format_value INDEX_JSON_ENABLED "$INDEX_JSON_ENABLED")"
  printf "\n"
  format_kv_plain "AUTO_FORMATTER_ENABLED" "$(format_value AUTO_FORMATTER_ENABLED "$AUTO_FORMATTER_ENABLED")"
  format_kv_plain "AUTO_FORMATTER_MODE" "$(format_value AUTO_FORMATTER_MODE "$AUTO_FORMATTER_MODE")"
  format_kv_plain "AUTO_FORMATTER_TEMPLATE" "$(format_value AUTO_FORMATTER_TEMPLATE "$AUTO_FORMATTER_TEMPLATE")"
  printf "\n"
  format_kv_plain "AUTO_SORTER_ENABLED" "$(format_value AUTO_SORTER_ENABLED "$AUTO_SORTER_ENABLED")"
  format_kv_plain "PERIODIC_SCAN_SECONDS" "$(format_value PERIODIC_SCAN_SECONDS "$PERIODIC_SCAN_SECONDS")"
  printf "\n"
}

build_content_lines_colored() {
  printf "%s\n" "HOMEBREW-STORE-CDN"
  printf "\n"
  format_kv_plain "BASE_URL" "$(format_value BASE_URL "$BASE_URL")"
  format_kv_plain "LOG_LEVEL" "$(format_value LOG_LEVEL "$LOG_LEVEL")"
  format_kv_plain "DATA_DIR" "$(format_value DATA_DIR "$DATA_DIR")"
  printf "\n"
  format_kv_plain "PKG_WATCHER_ENABLED" "$(format_value PKG_WATCHER_ENABLED "$PKG_WATCHER_ENABLED")"
  printf "\n"
  format_kv_colored \
    "AUTO_INDEXER_ENABLED" \
    "$(color_value "AUTO_INDEXER_ENABLED" "$COLOR_GREEN")" \
    "$(color_value "$(format_value AUTO_INDEXER_ENABLED "$AUTO_INDEXER_ENABLED")" "$COLOR_GREEN")"
  format_kv_colored \
    "INDEX_JSON_ENABLED" \
    "$(color_value "INDEX_JSON_ENABLED" "$COLOR_GREEN")" \
    "$(color_value "$(format_value INDEX_JSON_ENABLED "$INDEX_JSON_ENABLED")" "$COLOR_GREEN")"
  printf "\n"
  format_kv_colored \
    "AUTO_FORMATTER_ENABLED" \
    "$(color_value "AUTO_FORMATTER_ENABLED" "$COLOR_BLUE")" \
    "$(color_value "$(format_value AUTO_FORMATTER_ENABLED "$AUTO_FORMATTER_ENABLED")" "$COLOR_BLUE")"
  format_kv_colored \
    "AUTO_FORMATTER_MODE" \
    "$(color_value "AUTO_FORMATTER_MODE" "$COLOR_BLUE")" \
    "$(color_value "$(format_value AUTO_FORMATTER_MODE "$AUTO_FORMATTER_MODE")" "$COLOR_BLUE")"
  format_kv_colored \
    "AUTO_FORMATTER_TEMPLATE" \
    "$(color_value "AUTO_FORMATTER_TEMPLATE" "$COLOR_BLUE")" \
    "$(color_value "$(format_value AUTO_FORMATTER_TEMPLATE "$AUTO_FORMATTER_TEMPLATE")" "$COLOR_BLUE")"
  printf "\n"
  format_kv_colored \
    "AUTO_SORTER_ENABLED" \
    "$(color_value "AUTO_SORTER_ENABLED" "$COLOR_YELLOW")" \
    "$(color_value "$(format_value AUTO_SORTER_ENABLED "$AUTO_SORTER_ENABLED")" "$COLOR_YELLOW")"
  format_kv_colored \
    "PERIODIC_SCAN_SECONDS" \
    "$(color_value "PERIODIC_SCAN_SECONDS" "$COLOR_YELLOW")" \
    "$(color_value "$(format_value PERIODIC_SCAN_SECONDS "$PERIODIC_SCAN_SECONDS")" "$COLOR_YELLOW")"
  printf "\n"
}

initialize_data_dir(){
  log "Initializing directories and files..."
  initialized_any="false"
  create_path "$GAME_DIR" "game/" "$PKG_DIR/"
  create_path "$DLC_DIR" "dlc/" "$PKG_DIR/"
  create_path "$UPDATE_DIR" "update/" "$PKG_DIR/"
  create_path "$SAVE_DIR" "save/" "$PKG_DIR/"
  create_path "$UNKNOWN_DIR" "_unknown/" "$PKG_DIR/"
  create_path "$MEDIA_DIR" "_media/" "$DATA_DIR/"
  create_path "$CACHE_DIR" "_cache/" "$DATA_DIR/"
  create_path "$ERROR_DIR" "_error/" "$DATA_DIR/"
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
  pid INTEGER,
  id TEXT,
  name TEXT,
  "desc" TEXT,
  image TEXT,
  package TEXT,
  version TEXT,
  picpath TEXT,
  desc_1 TEXT,
  desc_2 TEXT,
  ReviewStars REAL,
  Size INTEGER,
  Author TEXT,
  apptype TEXT,
  pv TEXT,
  main_icon_path TEXT,
  main_menu_pic TEXT,
  releaseddate TEXT
);
SQL
}

compile_binaries() {
  tool_source="/app/lib/sfotool.c"
  tool_binary="/app/bin/sfotool"
  if [ ! -f "$tool_source" ]; then
    return
  fi
  if [ -f "$tool_binary" ]; then
    return
  fi
  if command -v cc >/dev/null 2>&1; then
    mkdir -p "/app/bin"
    if cc "$tool_source" -o "$tool_binary" >/dev/null 2>&1; then
      log "Compiled sfotool to $tool_binary"
    else
      log "Failed to compile sfotool"
    fi
  else
    log "cc not found; skipping sfotool compilation."
  fi
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

hostport="${BASE_URL#*://}"
hostport="${hostport%%/*}"
host="${hostport%%:*}"
port="${hostport##*:}"
if [ "$host" = "$hostport" ]; then
  port="80"
fi

clear_console
BOX_KEY_WIDTH=$(printf "%s\n" \
  "BASE_URL" \
  "LOG_LEVEL" \
  "DATA_DIR" \
  "PKG_WATCHER_ENABLED" \
  "AUTO_INDEXER_ENABLED" \
  "INDEX_JSON_ENABLED" \
  "AUTO_FORMATTER_ENABLED" \
  "AUTO_FORMATTER_MODE" \
  "AUTO_FORMATTER_TEMPLATE" \
  "AUTO_SORTER_ENABLED" \
  "PERIODIC_SCAN_SECONDS" \
  | awk '{ if (length($0) > max) max = length($0) } END { print max + 2 }')
BOX_CONTENT_WIDTH=$(build_content_lines_plain | awk '{ if (length($0) > max) max = length($0) } END { print max + 0 }')
BOX_WIDTH=$((BOX_CONTENT_WIDTH + 6))
box_border
build_content_lines_colored | while IFS= read -r line; do
  box_line "$line"
done
box_border

log "Starting NGINX..."
nginx
log "NGINX is running on ${host}:${port}"
log ""

initialize_data_dir
initialize_store_db
compile_binaries

log ""
if [ "$PKG_WATCHER_ENABLED" = "true" ]; then
  exec python3 -u /app/watcher.py \
    --base-url "$BASE_URL" \
    --log-level "$LOG_LEVEL" \
    --pkg-watcher-enabled "$PKG_WATCHER_ENABLED" \
    --auto-indexer-enabled "$AUTO_INDEXER_ENABLED" \
    --index-json-enabled "$INDEX_JSON_ENABLED" \
    --auto-formatter-enabled "$AUTO_FORMATTER_ENABLED" \
    --auto-sorter-enabled "$AUTO_SORTER_ENABLED" \
    --periodic-scan-seconds "$PERIODIC_SCAN_SECONDS" \
    --auto-formatter-mode "$AUTO_FORMATTER_MODE" \
    --auto-formatter-template "$AUTO_FORMATTER_TEMPLATE"
fi
log "PKG watcher is disabled."
exec tail -f /dev/null
