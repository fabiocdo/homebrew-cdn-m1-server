#!/bin/sh
set -eu

CONFIG_DIR="${CONFIG_DIR:-/app/configs}"
SETTINGS_FILE="${SETTINGS_FILE:-$CONFIG_DIR/settings.env}"
mkdir -p "$CONFIG_DIR"

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
python /app/main.py &
exec nginx -g 'daemon off;'
