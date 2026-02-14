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
# Watcher
# Operates scanning/sorting/indexing when true. Value type: boolean.
WATCHER_ENABLED=true
# Interval in seconds between directory scans. Value type: integer.
WATCHER_PERIODIC_SCAN_SECONDS=30
# Enable FPKGI format output. Value type: boolean.
FPGKI_FORMAT_ENABLED=false
# Generic timeout (seconds) for lightweight pkgtool commands.
PKGTOOL_TIMEOUT_SECONDS=300
# Base timeout (seconds) for pkg_validate.
PKGTOOL_VALIDATE_TIMEOUT_SECONDS=300
# Extra timeout budget by file size (seconds per GiB) for pkg_validate.
PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS=45
# Hard cap timeout (seconds) for pkg_validate. Set 0 to disable cap.
PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS=3600
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

: "${SERVER_IP:=127.0.0.1}"
: "${SERVER_PORT:=80}"
: "${ENABLE_TLS:=false}"
: "${LOG_LEVEL:=info}"
: "${WATCHER_ENABLED:=true}"
: "${WATCHER_PERIODIC_SCAN_SECONDS:=30}"
: "${FPGKI_FORMAT_ENABLED:=false}"
: "${PKGTOOL_TIMEOUT_SECONDS:=300}"
: "${PKGTOOL_VALIDATE_TIMEOUT_SECONDS:=300}"
: "${PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS:=45}"
: "${PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS:=3600}"

TLS_DIR="$CONFIG_DIR/certs"
TLS_CRT="${TLS_DIR}/tls.crt"
TLS_KEY="${TLS_DIR}/tls.key"

INIT_DB_SQL="/app/init/store_db.sql"

set +a

if [ ! -f "$INIT_DB_SQL" ]; then
  echo "[warn] init_db.sql not found at $INIT_DB_SQL; DB init may fail"
fi

# Prepare nginx runtime directories
mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi
mkdir -p /var/log/nginx /etc/nginx/conf.d
mkdir -p /app/data/_logs
mkdir -p /app/data/_cache

# Normalize the TLS toggle
ENABLE_TLS_LC="$(printf "%s" "$ENABLE_TLS" | tr '[:upper:]' '[:lower:]')"
if [ "$ENABLE_TLS_LC" = "true" ] || [ "$ENABLE_TLS_LC" = "1" ] || [ "$ENABLE_TLS_LC" = "yes" ]; then
  URL_SCHEME="https"
  DEFAULT_PORT="443"
else
  URL_SCHEME="http"
  DEFAULT_PORT="80"
fi
if [ "$SERVER_PORT" = "$DEFAULT_PORT" ]; then
  SERVER_URL="${URL_SCHEME}://${SERVER_IP}"
else
  SERVER_URL="${URL_SCHEME}://${SERVER_IP}:${SERVER_PORT}"
fi

GENERATED_AT="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
cat > /app/data/_cache/index.html <<EOF
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HB-Store CDN Status</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
      background: #f5f7fb;
      color: #1f2937;
      line-height: 1.5;
    }
    .wrap {
      max-width: 900px;
      margin: 32px auto;
      padding: 0 16px;
    }
    .card {
      background: #ffffff;
      border: 1px solid #dbe3ef;
      border-radius: 10px;
      padding: 20px;
      box-shadow: 0 2px 10px rgba(31, 41, 55, 0.06);
    }
    h1 { margin: 0 0 8px; font-size: 26px; }
    .ok {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: #dcfce7;
      color: #166534;
      font-weight: 600;
      margin-bottom: 14px;
    }
    .warn {
      background: #fef3c7;
      color: #92400e;
    }
    h2 { margin: 20px 0 8px; font-size: 18px; }
    ul { margin: 8px 0 0; padding-left: 20px; }
    code {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 4px;
      padding: 1px 5px;
    }
    .meta {
      margin-top: 16px;
      font-size: 13px;
      color: #4b5563;
    }
    a { color: #0f4db8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .toolbar {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }
    button {
      border: 1px solid #c7d2fe;
      background: #eef2ff;
      color: #1e3a8a;
      border-radius: 8px;
      padding: 6px 10px;
      cursor: pointer;
      font-weight: 600;
    }
    button:hover { background: #e0e7ff; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid #e5e7eb;
      padding: 8px 6px;
      text-align: left;
      vertical-align: top;
    }
    .badge {
      display: inline-block;
      min-width: 48px;
      text-align: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-weight: 700;
      font-size: 12px;
    }
    .up {
      background: #dcfce7;
      color: #166534;
    }
    .down {
      background: #fee2e2;
      color: #991b1b;
    }
    .unknown {
      background: #f3f4f6;
      color: #374151;
    }
    .small { font-size: 12px; color: #4b5563; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>HB-Store CDN</h1>
      <div class="ok">Status: ONLINE</div>

      <p>Base URL: <code>${SERVER_URL}</code></p>

      <h2>Health</h2>
      <ul>
        <li><a href="/health"><code>/health</code></a> - JSON service status.</li>
      </ul>

      <h2>Endpoint Healthcheck</h2>
      <div class="toolbar">
        <button type="button" id="refresh-health">Refresh checks</button>
        <span class="small" id="health-updated">Last update: pending...</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Path</th>
            <th>Status</th>
            <th>HTTP</th>
            <th>Type</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody id="health-table">
          <tr data-url="/health" data-required="true">
            <td><code>/health</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Required</td>
            <td>Service heartbeat.</td>
          </tr>
          <tr data-url="/store.db" data-required="true">
            <td><code>/store.db</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Required</td>
            <td>Main SQLite database.</td>
          </tr>
          <tr data-url="/api.php?db_check_hash=true" data-required="true">
            <td><code>/api.php?db_check_hash=true</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Required</td>
            <td>Returns DB MD5 hash for cache validation.</td>
          </tr>
          <tr data-url="/game.json" data-required="false">
            <td><code>/game.json</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Optional</td>
            <td>Generated only when FPKGI format is enabled and populated.</td>
          </tr>
          <tr data-url="/dlc.json" data-required="false">
            <td><code>/dlc.json</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Optional</td>
            <td>Generated only when FPKGI format is enabled and populated.</td>
          </tr>
          <tr data-url="/update/remote.md5" data-required="false">
            <td><code>/update/remote.md5</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Optional</td>
            <td>Store asset metadata file.</td>
          </tr>
          <tr data-url="/update/homebrew.elf" data-required="false">
            <td><code>/update/homebrew.elf</code></td>
            <td><span class="badge unknown">...</span></td>
            <td class="http">-</td>
            <td>Optional</td>
            <td>Store asset binary.</td>
          </tr>
        </tbody>
      </table>

      <h2>Main Endpoints</h2>
      <ul>
        <li><a href="/store.db"><code>/store.db</code></a> - SQLite database.</li>
        <li><a href="/api.php?db_check_hash=true"><code>/api.php?db_check_hash=true</code></a> - Returns <code>{"hash":"..."}</code>.</li>
        <li><a href="/api.php"><code>/api.php</code></a> - Optional JSON view from <code>_cache/store.db.json</code>.</li>
        <li><code>/download.php?tid=&lt;TITLE_ID&gt;&amp;check=true</code> - Returns <code>{"number_of_downloads":N}</code>.</li>
        <li><code>/download.php?tid=&lt;TITLE_ID&gt;</code> - Serves matching PKG file.</li>
        <li><a href="/update/remote.md5"><code>/update/remote.md5</code></a> - MD5 metadata.</li>
        <li><a href="/update/homebrew.elf"><code>/update/homebrew.elf</code></a> - Homebrew ELF binary.</li>
        <li><a href="/update/homebrew.elf.sig"><code>/update/homebrew.elf.sig</code></a> - Homebrew ELF signature.</li>
      </ul>

      <h2>PKG Content</h2>
      <ul>
        <li><code>/pkg/&lt;section&gt;/&lt;CONTENT_ID&gt;.pkg</code> - PKG files.</li>
        <li><code>/pkg/_media/&lt;CONTENT_ID&gt;_icon0.png</code> - media assets.</li>
        <li><code>/pkg/&lt;section&gt;.json</code> - optional fPKGi output when enabled.</li>
      </ul>

      <div class="meta">
        Generated at ${GENERATED_AT} by container entrypoint.
      </div>
    </div>
  </div>
  <script>
    (function () {
      function setRow(row, up, code) {
        var badge = row.querySelector(".badge");
        var http = row.querySelector(".http");
        if (!badge || !http) {
          return;
        }
        badge.classList.remove("up", "down", "unknown");
        if (up) {
          badge.textContent = "UP";
          badge.classList.add("up");
        } else {
          badge.textContent = "DOWN";
          badge.classList.add("down");
        }
        http.textContent = code;
      }

      async function checkRow(row) {
        var url = row.getAttribute("data-url");
        if (!url) {
          return;
        }
        try {
          var response = await fetch(url, { method: "HEAD", cache: "no-store" });
          if (response.status === 405) {
            response = await fetch(url, { method: "GET", cache: "no-store" });
          }
          setRow(row, response.ok, String(response.status));
        } catch (_err) {
          setRow(row, false, "ERR");
        }
      }

      async function runChecks() {
        var rows = Array.prototype.slice.call(document.querySelectorAll("#health-table tr"));
        for (var i = 0; i < rows.length; i += 1) {
          await checkRow(rows[i]);
        }
        var updated = document.getElementById("health-updated");
        if (updated) {
          updated.textContent = "Last update: " + new Date().toLocaleString();
        }
      }

      var button = document.getElementById("refresh-health");
      if (button) {
        button.addEventListener("click", function () {
          runChecks();
        });
      }
      runChecks();
    })();
  </script>
</body>
</html>
EOF

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
python -u -m hb_store_m1 &
exec nginx -g 'daemon off;'
