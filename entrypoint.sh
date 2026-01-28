#!/bin/sh
set -e

TERM="${TERM:-xterm}"
export TERM

# DEFAULT ENVIRONMENT VARIABLES
DEFAULT_BASE_URL="http://127.0.0.1:8080"
DEFAULT_LOG_LEVEL="info"
DEFAULT_PKG_WATCHER_ENABLED="true"
DEFAULT_AUTO_INDEXER_ENABLED="true"
DEFAULT_AUTO_RENAMER_ENABLED="false"
DEFAULT_AUTO_RENAMER_TEMPLATE="{title} [{titleid}][{apptype}]"
DEFAULT_AUTO_RENAMER_MODE="none"
DEFAULT_AUTO_RENAMER_EXCLUDED_DIRS="app"
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
use_default_if_unset LOG_LEVEL "$DEFAULT_LOG_LEVEL"
use_default_if_unset PKG_WATCHER_ENABLED "$DEFAULT_PKG_WATCHER_ENABLED"
use_default_if_unset AUTO_INDEXER_ENABLED "$DEFAULT_AUTO_INDEXER_ENABLED"
use_default_if_unset AUTO_RENAMER_ENABLED "$DEFAULT_AUTO_RENAMER_ENABLED"
use_default_if_unset AUTO_MOVER_ENABLED "$DEFAULT_AUTO_MOVER_ENABLED"
use_default_if_unset AUTO_RENAMER_MODE "$DEFAULT_AUTO_RENAMER_MODE"
use_default_if_unset AUTO_RENAMER_TEMPLATE "$DEFAULT_AUTO_RENAMER_TEMPLATE"
use_default_if_unset AUTO_RENAMER_EXCLUDED_DIRS "$DEFAULT_AUTO_RENAMER_EXCLUDED_DIRS"
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

format_kv() {
  key="$1"
  value="$2"
  key_pad=$((BOX_KEY_WIDTH - ${#key}))
  if [ "$key_pad" -lt 1 ]; then
    key_pad=1
  fi
  printf "%s%*s%s" "$key" "$key_pad" "" "$value"
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
  echo "HOMEBREW-STORE-CDN"
  echo ""
  echo "$(format_kv "BASE_URL" "$(format_value BASE_URL "$BASE_URL")")"
  echo "$(format_kv "LOG_LEVEL" "$(format_value LOG_LEVEL "$LOG_LEVEL")")"
  echo ""
  echo "$(format_kv "PKG_WATCHER_ENABLED" "$(format_value PKG_WATCHER_ENABLED "$PKG_WATCHER_ENABLED")")"
  echo ""
  echo "$(format_kv "AUTO_INDEXER_ENABLED" "$(format_value AUTO_INDEXER_ENABLED "$AUTO_INDEXER_ENABLED")")"
  echo ""
  echo "$(format_kv "AUTO_RENAMER_ENABLED" "$(format_value AUTO_RENAMER_ENABLED "$AUTO_RENAMER_ENABLED")")"
  echo "$(format_kv "AUTO_RENAMER_MODE" "$(format_value AUTO_RENAMER_MODE "$AUTO_RENAMER_MODE")")"
  echo "$(format_kv "AUTO_RENAMER_TEMPLATE" "$(format_value AUTO_RENAMER_TEMPLATE "$AUTO_RENAMER_TEMPLATE")")"
  echo "$(format_kv "AUTO_RENAMER_EXCLUDED_DIRS" "$(format_value AUTO_RENAMER_EXCLUDED_DIRS "$AUTO_RENAMER_EXCLUDED_DIRS")")"
  echo ""
  echo "$(format_kv "AUTO_MOVER_ENABLED" "$(format_value AUTO_MOVER_ENABLED "$AUTO_MOVER_ENABLED")")"
  echo "$(format_kv "AUTO_MOVER_EXCLUDED_DIRS" "$(format_value AUTO_MOVER_EXCLUDED_DIRS "$AUTO_MOVER_EXCLUDED_DIRS")")"
  echo ""
}

build_content_lines_colored() {
  echo "HOMEBREW-STORE-CDN"
  echo ""
  echo "$(format_kv "BASE_URL" "$(format_value BASE_URL "$BASE_URL")")"
  echo "$(format_kv "LOG_LEVEL" "$(format_value LOG_LEVEL "$LOG_LEVEL")")"
  echo ""
  echo "$(format_kv "PKG_WATCHER_ENABLED" "$(format_value PKG_WATCHER_ENABLED "$PKG_WATCHER_ENABLED")")"
  echo ""
  echo "$(format_kv "$(color_value "AUTO_INDEXER_ENABLED" "\033[0;92m")" "$(color_value "$(format_value AUTO_INDEXER_ENABLED "$AUTO_INDEXER_ENABLED")" "\033[0;92m")")"
  echo ""
  echo "$(format_kv "$(color_value "AUTO_RENAMER_ENABLED" "\033[1;94m")" "$(color_value "$(format_value AUTO_RENAMER_ENABLED "$AUTO_RENAMER_ENABLED")" "\033[1;94m")")"
  echo "$(format_kv "$(color_value "AUTO_RENAMER_MODE" "\033[1;94m")" "$(color_value "$(format_value AUTO_RENAMER_MODE "$AUTO_RENAMER_MODE")" "\033[1;94m")")"
  echo "$(format_kv "$(color_value "AUTO_RENAMER_TEMPLATE" "\033[1;94m")" "$(color_value "$(format_value AUTO_RENAMER_TEMPLATE "$AUTO_RENAMER_TEMPLATE")" "\033[1;94m")")"
  echo "$(format_kv "$(color_value "AUTO_RENAMER_EXCLUDED_DIRS" "\033[1;94m")" "$(color_value "$(format_value AUTO_RENAMER_EXCLUDED_DIRS "$AUTO_RENAMER_EXCLUDED_DIRS")" "\033[1;94m")")"
  echo ""
  echo "$(format_kv "$(color_value "AUTO_MOVER_ENABLED" "\033[1;94m")" "$(color_value "$(format_value AUTO_MOVER_ENABLED "$AUTO_MOVER_ENABLED")" "\033[1;94m")")"
  echo "$(format_kv "$(color_value "AUTO_MOVER_EXCLUDED_DIRS" "\033[1;94m")" "$(color_value "$(format_value AUTO_MOVER_EXCLUDED_DIRS "$AUTO_MOVER_EXCLUDED_DIRS")" "\033[1;94m")")"
  echo ""
}

initialize_dir(){
  log "Initializing directories and files..."
  initialized_any="false"
  create_path "$PKG_DIR/game" "game/" "$PKG_DIR/"
  create_path "$PKG_DIR/dlc" "dlc/" "$PKG_DIR/"
  create_path "$PKG_DIR/update" "update/" "$PKG_DIR/"
  create_path "$PKG_DIR/app" "app/" "$PKG_DIR/"
  create_path "$MEDIA_DIR" "_media/" "$DATA_DIR/"
  create_path "$CACHE_DIR" "_cache/" "$DATA_DIR/"
  create_path "$DATA_DIR/_errors" "_errors/" "$DATA_DIR/"
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
log "Starting NGINX..."
nginx
log "NGINX is running on ${host}:${port}"

log ""
BOX_KEY_WIDTH=28
BOX_CONTENT_WIDTH=$(build_content_lines_plain | awk '{ if (length($0) > max) max = length($0) } END { print max + 0 }')
BOX_WIDTH=$((BOX_CONTENT_WIDTH + 6))
box_border
build_content_lines_colored | while IFS= read -r line; do
  box_line "$line"
done
box_border
log ""

initialize_dir

log ""
if [ "$PKG_WATCHER_ENABLED" = "true" ]; then
  exec python3 -u /scripts/watcher.py \
    --base-url "$BASE_URL" \
    --log-level "$LOG_LEVEL" \
    --pkg-watcher-enabled "$PKG_WATCHER_ENABLED" \
    --auto-indexer-enabled "$AUTO_INDEXER_ENABLED" \
    --auto-renamer-enabled "$AUTO_RENAMER_ENABLED" \
    --auto-mover-enabled "$AUTO_MOVER_ENABLED" \
    --auto-renamer-mode "$AUTO_RENAMER_MODE" \
    --auto-renamer-template "$AUTO_RENAMER_TEMPLATE" \
    --auto-renamer-excluded-dirs "$AUTO_RENAMER_EXCLUDED_DIRS" \
    --auto-mover-excluded-dirs "$AUTO_MOVER_EXCLUDED_DIRS"
fi
log "PKG watcher is disabled."
exec tail -f /dev/null
