#!/bin/sh
set -eu

rm -f /etc/nginx/conf.d/default.conf

OUT_SERVERS="/etc/nginx/conf.d/servers.conf"
COMMON="/etc/nginx/templates/common.locations.conf"

ENABLE_TLS="${ENABLE_TLS:-false}"
CERT_CRT="${CERT_CRT:-/etc/nginx/certs/localhost.crt}"
CERT_KEY="${CERT_KEY:-/etc/nginx/certs/localhost.key}"

COMMON_LOCATIONS="$(cat "$COMMON")"

LIMITS_BLOCK='
  limit_conn perip 12;
  limit_conn perserver 80;
'

if [ "$ENABLE_TLS" = "true" ]; then
  if [ ! -f "$CERT_CRT" ] || [ ! -f "$CERT_KEY" ]; then
    echo "[nginx] ENABLE_TLS=true but cert files missing:"
    echo "  CRT: $CERT_CRT"
    echo "  KEY: $CERT_KEY"
    exit 1
  fi

  cat > "$OUT_SERVERS" <<EOF
server {
  listen 80;
  server_name _;
$LIMITS_BLOCK
  return 301 https://\$host\$request_uri;
}

server {
  listen 443 ssl;
  server_name _;
$LIMITS_BLOCK

  ssl_certificate     $CERT_CRT;
  ssl_certificate_key $CERT_KEY;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_prefer_server_ciphers on;

$COMMON_LOCATIONS
}
EOF

  echo "[nginx] wrote $OUT_SERVERS (ENABLE_TLS=true)"
else
  cat > "$OUT_SERVERS" <<EOF
server {
  listen 80;
  server_name _;
$LIMITS_BLOCK

$COMMON_LOCATIONS
}
EOF

  echo "[nginx] wrote $OUT_SERVERS (ENABLE_TLS=false)"
fi
