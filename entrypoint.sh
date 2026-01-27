#!/bin/sh
set -e

python3 /generate-index.py &

echo "[·] Starting NGINX..."
exec nginx -g "daemon off;"
