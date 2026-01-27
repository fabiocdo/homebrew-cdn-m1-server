#!/bin/sh
set -e

BASE_URL=${BASE_URL:-'http://127.0.0.1:8080'}
AUTO_GENERATE_JSON_PERIOD=${AUTO_GENERATE_JSON_PERIOD:-'2'}
AUTO_RENAME_PKGS=${AUTO_RENAME_PKGS:-'false'}
AUTO_RENAME_TEMPLATE=${AUTO_RENAME_TEMPLATE:-'{title} [{titleid}][{apptype}]'}
AUTO_RENAME_TITLE_MODE=${AUTO_RENAME_TITLE_MODE:-'none'}

log() {
  printf "%s\n" "$*"
}

hostport="${BASE_URL#*://}"
hostport="${hostport%%/*}"
host="${hostport%%:*}"
port="${hostport##*:}"
if [ "$host" = "$hostport" ]; then
  port="80"
fi

log "Starting NGINX on ${host}:${port}..."
nginx
log "Started NGINX on ${host}:${port}."

log "Starting indexer: python3 /generate-index.py --base-url \"$BASE_URL\" --auto-generate-json-period \"$AUTO_GENERATE_JSON_PERIOD\" --auto-rename-pkgs \"$AUTO_RENAME_PKGS\" --auto-rename-template \"$AUTO_RENAME_TEMPLATE\" --auto-rename-title-mode \"$AUTO_RENAME_TITLE_MODE\""
exec python3 /generate-index.py \
  --base-url "$BASE_URL" \
  --auto-generate-json-period "$AUTO_GENERATE_JSON_PERIOD" \
  --auto-rename-pkgs "$AUTO_RENAME_PKGS" \
  --auto-rename-template "$AUTO_RENAME_TEMPLATE" \
  --auto-rename-title-mode "$AUTO_RENAME_TITLE_MODE"
