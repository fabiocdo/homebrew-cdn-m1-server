# homebrew-cdn-m1-server

PS4 static CDN pipeline for `hb-store` (`store.db`) and `fPKGi` (`*.json`).

## What it does

1. Watches `data/share/pkg/**/*.pkg` on a reconcile schedule.
2. Probes each PKG with `pkgtool` (`PARAM.SFO` + media).
3. Moves PKG to canonical path: `data/share/pkg/<app_type>/<CONTENT_ID>.pkg`.
4. Upserts full metadata into internal catalog: `data/internal/catalog/catalog.db`.
5. Exports selected targets:
   - `hb-store` -> `data/share/hb-store/store.db`
   - `fpkgi` -> `data/share/fpkgi/*.json`
6. Serves public content through nginx from `data/share`.

Broken PKGs are moved to `data/internal/errors`.

## Quick start (Docker Compose)

### 1) Prepare config

Copy defaults:

```bash
cp init/settings.ini configs/settings.ini
```

Edit `configs/settings.ini` as needed:

```ini
# Leave any value empty to set it as null (no implicit default).
# Host clients use to reach the service. Value type: string.
SERVER_IP=127.0.0.1
# Port that nginx listens on inside the container. Leave empty to set null. Value type: integer.
SERVER_PORT=80
# Set true to serve TLS/HTTPS; If enabled, "tls.crt" and "tls.key" are required and must live under configs/certs/. Value type: boolean.
ENABLE_TLS=false
# Logging verbosity (debug | info | warn | error). Value type: string.
LOG_LEVEL=info
# Keep 1 to disable parallel preprocessing.
RECONCILE_PKG_PREPROCESS_WORKERS=1
# Cron expression for reconcile schedule (use https://crontab.guru/). Value type: string.
RECONCILE_CRON_EXPRESSION=*/5 * * * *
# Comma-separated export targets. Supported: hb-store, fpkgi.
EXPORT_TARGETS=hb-store,fpkgi
# Generic timeout (seconds) for lightweight pkgtool commands.
PKGTOOL_TIMEOUT_SECONDS=300
```

If `ENABLE_TLS=true`, place cert files in `configs/certs/`:

- `configs/certs/tls.crt`
- `configs/certs/tls.key`

### 2) Put your PKGs

Drop PKGs under:

- `data/share/pkg/`

The worker scans recursively (except `data/share/pkg/media`) and reorganizes to canonical folders (`app`, `game`, `dlc`, `update`, `save`, `unknown`).

### 3) Run

```bash
docker compose up --build -d
docker compose logs -f homebrew-cdn-m1-server
```

### 4) Validate service health in browser

Open in your browser:

- `http://<SERVER_IP>:<SERVER_PORT>/` when `ENABLE_TLS=false`
- `https://<SERVER_IP>:<SERVER_PORT>/` when `ENABLE_TLS=true`
- If `SERVER_PORT` is null/empty, omit `:<SERVER_PORT>`.

The page must load and show the CDN health/status screen.

### 5) Check outputs

Public share root:

- `data/share/index.html`
- `data/share/hb-store/store.db` (served as `/store.db`)
- `data/share/pkg/**`
- `data/share/hb-store/update/homebrew.elf`
- `data/share/hb-store/update/homebrew.elf.sig`
- `data/share/hb-store/update/remote.md5`
- `data/share/fpkgi/*.json`

Internal (not public):

- `data/internal/catalog/catalog.db`
- `data/internal/catalog/pkgs-snapshot.json`
- `data/internal/errors/*`
- `data/internal/logs/app_errors.log`
