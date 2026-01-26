#!/bin/sh
set -e

PKG_DIR="/data/pkg"
MEDIA_DIR="/data/_media"
ICONS_DIR="/data/_media/icons"

generate() {
  echo "[+] Generating index.json..."
  mkdir -p "$PKG_DIR" "$ICONS_DIR"
  python3 /generate-index.py
}

# Initial generation
if [ -d "$PKG_DIR" ]; then
  generate
fi

# Automatic watcher
if [ -d "$PKG_DIR" ]; then
  inotifywait -m -e create -e delete -e move -e close_write "$PKG_DIR" | while read _; do
    echo "[*] Change detected in pkg/"
    generate
  done &
fi

echo "[+] Starting NGINX..."
exec nginx -g "daemon off;"
