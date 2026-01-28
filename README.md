# homebrew-store-cdn

Local CDN for PS4 homebrew packages using Docker Compose and Nginx, with automatic
index generation and icon extraction.

## What it does

- Serves `.pkg` files over HTTP.
- Generates `index.json` for Homebrew Store clients.
- Extracts `icon0.png` from each PKG and serves it from `_media`.
- Organizes PKGs into `game/`, `update/`, `dlc/`, and `app/` folders.
- Watches the `pkg/` tree and refreshes `index.json` after file changes (with a debounce).

## Requirements

- Docker + Docker Compose
- A host directory to store PKGs and generated assets

## Quick start

### Option A: Docker Run (from Docker Hub)

```bash
docker run -d \
  --name homebrew-store-cdn \
  -p 8080:80 \
  -e BASE_URL=http://127.0.0.1:8080 \
  -e PKG_WATCHER_ENABLED=true \
  -e AUTO_INDEXER_ENABLED=true \
  -e AUTO_INDEXER_DEBOUNCE_TIME_SECONDS=2 \
  -e AUTO_RENAMER_ENABLED=false \
  -e AUTO_RENAMER_TEMPLATE="{title} [{titleid}][{apptype}]" \
  -e AUTO_RENAMER_MODE=none \
  -e AUTO_MOVER_ENABLED=true \
  -e AUTO_MOVER_EXCLUDED_DIRS=app \
  -v ./data:/data \
  -v ./nginx.conf:/etc/nginx/nginx.conf:ro \
  fabiocdo/homebrew-store-cdn:latest
```

### Option B: Docker Compose (from Docker Hub)

Create a `docker-compose.yml` (see example folder):

```yaml
services:
  homebrew-store-cdn:
    image: fabiocdo/homebrew-store-cdn:latest
    container_name: homebrew-store-cdn
    ports:
      - "8080:80"
    environment:
      - BASE_URL=http://127.0.0.1:8080
      - PKG_WATCHER_ENABLED=true
      - AUTO_INDEXER_ENABLED=true
      - AUTO_INDEXER_DEBOUNCE_TIME_SECONDS=2
      - AUTO_RENAMER_ENABLED=false
      - AUTO_RENAMER_TEMPLATE={title} [{titleid}][{apptype}]
      - AUTO_RENAMER_MODE=none
      - AUTO_MOVER_ENABLED=true
      - AUTO_MOVER_EXCLUDED_DIRS=app
    volumes:
      - ./data:/data
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    restart: unless-stopped
```

Run:

```bash
docker compose up -d
```

### Option C: Build locally

1) Edit the `environment:` and `volumes:` sections in your `docker-compose.yml`
   (see example folder).

2) Build and run:

```bash
docker compose build
docker compose up -d
```

### Option D: Run locally using the example compose file

1) Copy the example compose file to the repo root:

```bash
cp example/docker-compose.yml ./docker-compose.yml
```

2) Edit the `environment:` and `volumes:` sections in `docker-compose.yml`
   if needed.

3) Build and run:

```bash
docker compose up -d --build
```

Open:

- http://127.0.0.1:8080
- http://127.0.0.1:8080/index.json

## Host data layout

The host directory mapped to `/data` must follow this layout:

```
/opt/cdn/
|-- pkg/                   # Place PKGs here
|   |-- game/              # Auto-created
|   |-- update/            # Auto-created
|   |-- dlc/               # Auto-created
|   |-- app/               # Auto-created (no auto-move)
|   |-- _PUT_YOUR_PKGS_HERE
|   |-- Game Name [CUSA12345].pkg
|-- _media/                # Auto-generated icons
|   |-- CUSA12345.png
|-- _cache/                # Auto-generated cache
|   |-- index-cache.json
|-- index.json             # Auto-generated index
```

Notes:

- `index.json` and `_media/*.png` are generated automatically.
- The tool ignores any PKG located inside folders that start with `_`.
- The `_PUT_YOUR_PKGS_HERE` file is a marker created on container startup.
- Auto-created folders and the marker are only created during container startup.
- `_cache/index-cache.json` stores metadata to speed up subsequent runs.
- The cache is updated only when `index.json` is generated.
- If a duplicate target name is detected, the cycle is skipped and no new `index.json` is written.

## Package organization

During indexing, packages are classified by their `CATEGORY` from `param.sfo`:

- `gd` -> `game`
- `gp` -> `update`
- `ac` -> `dlc`
- `ap`, `ad`, `al`, `bd` -> `app`

Packages placed under `pkg/app` are always indexed as:

- `apptype: "app"`
- `category: "ap"`

The container never auto-moves files inside `pkg/app`.

## index.json format

Example entry:

```json
{
  "id": "CUSA12345",
  "name": "Example Game",
  "version": "1.00",
  "apptype": "game",
  "pkg": "http://127.0.0.1:8080/pkg/game/Example%20Game%20%5BCUSA12345%5D.pkg",
  "icon": "http://127.0.0.1:8080/_media/CUSA12345.png",
  "category": "gd",
  "region": "EUR"
}
```

Fields:

- `id`, `name`, `version`: extracted from `param.sfo`.
- `apptype`: derived from `CATEGORY` or forced to `app` for `pkg/app`.
- `pkg`, `icon`: URLs built from `BASE_URL`.
- `category`: optional, only when present.
- `region`: optional, derived from `CONTENT_ID`.

## Environment variables

| Variable                    | Description                                                                                                              | Default                          |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------------|----------------------------------|
| `BASE_URL`                  | Base URL written in `index.json`.                                                                                        | `http://127.0.0.1:8080`          |
| `CDN_DATA_DIR`              | Host path mapped to `/data`.                                                                                             | `./data`                         |
| `PKG_WATCHER_ENABLED` | Master switch for watcher-driven automations (rename, move, index).                                                   | `true`                           |
| `AUTO_INDEXER_ENABLED`      | Enable auto-generated `index.json` and cache updates.                                                                    | `true`                           |
| `AUTO_INDEXER_DEBOUNCE_TIME_SECONDS` | Delay (seconds) before regenerating `index.json` after changes.                                              | `2`                              |
| `AUTO_RENAMER_ENABLED`      | Enable PKG rename using `AUTO_RENAMER_TEMPLATE`.                                                                         | `false`                          |
| `AUTO_RENAMER_TEMPLATE`     | Template using `{title}`, `{titleid}`, `{region}`, `{apptype}`, `{version}`, `{category}`, `{content_id}`, `{app_type}`. | `{title} [{titleid}][{apptype}]` |
| `AUTO_RENAMER_MODE`         | Title transform mode for `{title}`: `none`, `uppercase`, `lowercase`, `capitalize`.                                      | `none`                           |
| `AUTO_MOVER_ENABLED`        | Enable auto-moving PKGs into `game/`, `dlc/`, `update/` folders.                                                         | `true`                           |
| `AUTO_MOVER_EXCLUDED_DIRS`  | Comma-separated directory names to skip when auto-moving.                                                                | `app`                            |

Dependencies and behavior:

- `PKG_WATCHER_ENABLED=false` disables all automations (rename, move, index) and the watcher does not start.
- `AUTO_INDEXER_DEBOUNCE_TIME_SECONDS` only applies when `AUTO_INDEXER_ENABLED=true` and the watcher is enabled.
- `AUTO_RENAMER_TEMPLATE` and `AUTO_RENAMER_MODE` only apply when `AUTO_RENAMER_ENABLED=true` and the watcher is enabled.
- `AUTO_MOVER_EXCLUDED_DIRS` only applies when `AUTO_MOVER_ENABLED=true` and the watcher is enabled.

## Volume config

| Volume                                  | Description                              | Default        |
|-----------------------------------------|------------------------------------------|----------------|
| `./data:/data`                          | Host data directory mapped to `/data`.   | `./data`       |
| `./nginx.conf:/etc/nginx/nginx.conf:ro` | External Nginx config mounted read-only. | `./nginx.conf` |

## Nginx behavior

- Serves `/data` directly.
- Adds cache headers for `.pkg`, `.zip`, and image files.
- Supports HTTP range requests for large downloads.

If you want to provide your own `nginx.conf`, mount it to `/etc/nginx/nginx.conf:ro`
as shown in the quick start examples.

## Troubleshooting

- If a PKG is encrypted, `pkgtool` may fail to read `param.sfo` and indexing will stop.
- If icons are missing, ensure the PKG contains `ICON0_PNG` or `PIC0_PNG`.
- If you see `Duplicate target exists, skipping`, the cycle will not regenerate `index.json` until the conflict is
  resolved.

## Developer notes

- The orchestrator runs as `/scripts/watcher.py` inside the container.
- Shared constants and paths live in `scripts/settings.py`.
- Shared log helpers live in `scripts/utils/log_utils.py`.
- Indexer internals are split into `scripts/auto_indexer.py`, `scripts/auto_mover.py`,
  `scripts/auto_renamer.py`, `scripts/utils/pkg_utils.py`, `scripts/utils/pkgtool.py`,
  and `scripts/watcher.py`.
- Runtime indexer config is stored in `scripts/settings.py`.
- CLI option specs live in `scripts/settings.py` as `CLI_ARGS`.
- Indexer logs use Python's `logging` with `[+]`/`[*]` prefixes.
