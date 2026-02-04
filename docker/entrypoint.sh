#!/bin/sh
set -eu

CONFIG_DIR="${CONFIG_DIR:-/app/configs}"
SETTINGS_FILE="${SETTINGS_FILE:-$CONFIG_DIR/settings.env}"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/certs"

# If the settings file is missing, write a minimal default so Docker Compose can boot right away.
if [ ! -f "$SETTINGS_FILE" ]; then
  cat <<'EOF' > "$SETTINGS_FILE"
# Minimal configuration; edit SERVER_* and ENABLE_SSL to match your environment.

# Server Configuration
# SERVER_IP: Host that clients use to reach the service.
# SERVER_PORT: Port that nginx listens on inside the container.
# ENABLE_SSL: Set true to serve HTTPS; tls.crt/tls.key must live under configs/certs/.
# LOG_LEVEL: Logging verbosity (debug/info/warn/error).
SERVER_IP=0.0.0.0
SERVER_PORT=80
ENABLE_SSL=false
LOG_LEVEL=info

WATCHER_ENABLED=true         # Set false to pause automatic scanning/sorting/indexing.
WATCHER_PERIODIC_SCAN_SECONDS=30
WATCHER_SCAN_BATCH_SIZE=50
WATCHER_EXECUTOR_WORKERS=4
WATCHER_SCAN_WORKERS=4
WATCHER_ACCESS_LOG_TAIL=true  # Tail nginx access.log (set false to skip).
WATCHER_ACCESS_LOG_INTERVAL=5
AUTO_INDEXER_OUTPUT_FORMAT=db,json  # Comma-separated: include JSON to write index.json, include db to update store.db.
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
: "${ENABLE_SSL:=false}"

TLS_DIR="${TLS_DIR:-$CONFIG_DIR/certs}"
: "${TLS_CRT:=${TLS_DIR}/tls.crt}"
: "${TLS_KEY:=${TLS_DIR}/tls.key}"

set +a

# Prepare nginx runtime directories
mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi
mkdir -p /var/log/nginx /etc/nginx/conf.d

# Normalize ENABLE_SSL to lowercase for comparison
ENABLE_SSL_LC="$(printf "%s" "$ENABLE_SSL" | tr '[:upper:]' '[:lower:]')"

# Build the appropriate server block
if [ "$ENABLE_SSL_LC" = "true" ] || [ "$ENABLE_SSL_LC" = "1" ] || [ "$ENABLE_SSL_LC" = "yes" ]; then
  if [ ! -f "$TLS_CRT" ] || [ ! -f "$TLS_KEY" ]; then
    echo "[FATAL] ENABLE_SSL=true but cert/key missing:"
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
python -m main &
exec nginx -g 'daemon off;'
