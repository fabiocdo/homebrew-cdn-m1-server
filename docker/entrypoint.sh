#!/bin/sh
set -eu

CONFIG_DIR="${CONFIG_DIR:-/app/configs}"
SETTINGS_FILE="${SETTINGS_FILE:-$CONFIG_DIR/settings.env}"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/certs"

# If the settings file is missing, write a minimal default so Docker Compose can boot right away.
if [ ! -f "$SETTINGS_FILE" ]; then
  cat <<'EOF' > "$SETTINGS_FILE"
# Server Configuration
# Host clients use to reach the service. Value type: string.
SERVER_IP=127.0.0.1
# Port that nginx listens on inside the container. Value type: integer.
SERVER_PORT=80
# Set true to serve TLS/HTTPS; If enabled, "tls.crt" and "tls.key" are required and must live under configs/certs/. Value type: boolean.
ENABLE_TLS=false
# Logging verbosity (debug | info | warn | error). Value type: string.
LOG_LEVEL=info

# CDN Automation
# Operates scanning/sorting/indexing when true. Value type: boolean.
WATCHER_ENABLED=true
# Interval in seconds between directory scans. Value type: integer.
WATCHER_PERIODIC_SCAN_SECONDS=30
# Number of PKGs processed per batch; larger values reduce scan frequency. Value type: integer.
WATCHER_SCAN_BATCH_SIZE=50
# Parallel workers handling planned PKG operations. Value type: integer.
WATCHER_EXECUTOR_WORKERS=4
# Parallel workers scanning PKGs for metadata changes. Value type: integer.
WATCHER_SCAN_WORKERS=4
# Tail nginx access.log (set false to skip). Value type: boolean.
WATCHER_ACCESS_LOG_TAIL=true
# Seconds between access-log tail outputs. Value type: integer.
WATCHER_ACCESS_LOG_INTERVAL=5
# Comma-separated list (DB | JSON); include `JSON` to write index.json and `DB` to update store.db. Value type: string list.
AUTO_INDEXER_OUTPUT_FORMAT=DB,JSON
EOF
  echo "[info] Generated default settings.env at $SETTINGS_FILE"
fi

# Load user settings and keep defaults exported
set -a
if [ -f "$SETTINGS_FILE" ]; then
  # shellcheck source=/dev/null
  . "$SETTINGS_FILE"
else
  echo "[warn] settings.env not found at $SETTINGS_FILE; using defaults"
fi

: "${SERVER_IP:=0.0.0.0}"
: "${SERVER_PORT:=80}"
: "${ENABLE_TLS:=false}"

TLS_DIR="${TLS_DIR:-$CONFIG_DIR/certs}"
: "${TLS_CRT:=${TLS_DIR}/tls.crt}"
: "${TLS_KEY:=${TLS_DIR}/tls.key}"

: "${INIT_DB_SQL:=/app/init/store_db.sql}"
: "${INIT_TEMPLATE_JSON:=/app/init/template.json}"

set +a

if [ ! -f "$INIT_DB_SQL" ]; then
  echo "[warn] init_db.sql not found at $INIT_DB_SQL; DB init may fail"
fi

# Prepare nginx runtime directories
mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi
mkdir -p /var/log/nginx /etc/nginx/conf.d

# Normalize the TLS toggle
ENABLE_TLS_LC="$(printf "%s" "$ENABLE_TLS" | tr '[:upper:]' '[:lower:]')"

# Build the appropriate server block
if [ "$ENABLE_TLS_LC" = "true" ] || [ "$ENABLE_TLS_LC" = "1" ] || [ "$ENABLE_TLS_LC" = "yes" ]; then
  if [ ! -f "$TLS_CRT" ] || [ ! -f "$TLS_KEY" ]; then
    echo "[FATAL] ENABLE_TLS=true but cert/key missing:"
    echo "        TLS_CRT=$TLS_CRT"
    echo "        TLS_KEY=$TLS_KEY"
    exit 1
  fi

  cat > /etc/nginx/conf.d/servers.conf <<EOF
server {
  listen ${SERVER_PORT} ssl;
  listen [::]:${SERVER_PORT} ssl;
  server_name _;

  ssl_certificate     ${TLS_CRT};
  ssl_certificate_key ${TLS_KEY};

  include /etc/nginx/templates/common.locations.conf;
}
EOF
else
  cat > /etc/nginx/conf.d/servers.conf <<EOF
server {
  listen ${SERVER_PORT};
  listen [::]:${SERVER_PORT};
  server_name _;

  include /etc/nginx/templates/common.locations.conf;
}
EOF
fi

# Validate nginx configuration
nginx -t

# Start the watcher (background) and run nginx in the foreground
python -m hb_store_m1 &
exec nginx -g 'daemon off;'
