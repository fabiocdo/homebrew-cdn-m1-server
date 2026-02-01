# homebrew-store-cdn

Local CDN for PS4 homebrew packages using Docker Compose and Nginx, with automatic
index generation and icon extraction.

## What it does

- Serves `.pkg` files over HTTP.
- Generates `index.json` for Homebrew Store clients.
- Extracts `icon0.png` from each PKG and serves it from `_media`.
- Organizes PKGs into `game/`, `update/`, `dlc/`, and `app/` folders.
- Moves files with rename/move conflicts into `_errors/`.
- Watches the `pkg/` tree and refreshes `index.json` after file changes.

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
  -e LOG_LEVEL=info \
  -e PKG_WATCHER_ENABLED=true \
  -e AUTO_INDEXER_ENABLED=true \
  -e INDEX_JSON_ENABLED=false \
  -e AUTO_FORMATTER_ENABLED=true \
  -e AUTO_FORMATTER_MODE=none \
  -e AUTO_FORMATTER_TEMPLATE="{title} [{titleid}][{apptype}]" \
  -e AUTO_SORTER_ENABLED=true \
  -e PERIODIC_SCAN_SECONDS=30 \
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
      - LOG_LEVEL=info
      - PKG_WATCHER_ENABLED=true
      - AUTO_INDEXER_ENABLED=true
      - INDEX_JSON_ENABLED=false
      - AUTO_FORMATTER_ENABLED=true
      - AUTO_FORMATTER_MODE=none
      - AUTO_FORMATTER_TEMPLATE={title} [{titleid}][{apptype}]
      - AUTO_SORTER_ENABLED=true
      - PERIODIC_SCAN_SECONDS=30
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
|-- _errors/               # Files moved when rename/move conflicts occur
|-- index.json             # Auto-generated index
```

Notes:

- `index.json` and `_media/*.png` are generated automatically.
- PKGs are processed even if they are inside folders that start with `_`.
- PKGs placed directly in `pkg/` are processed by formatter/sorter but are not indexed.
- The `_PUT_YOUR_PKGS_HERE` file is a marker created on container startup.
- Auto-created folders and the marker are only created during container startup.
- `_cache/index-cache.json` stores metadata to speed up subsequent runs.
- The cache is updated only when `index.json` is generated.
- If a duplicate target name is detected, the file is moved to `_errors/`.

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
| `LOG_LEVEL`                 | Log verbosity: `debug`, `info`, `warn`, `error`.                                                                          | `info`                           |
| `PKG_WATCHER_ENABLED`       | Master switch for watcher-driven automations (format, move, index).                                                     | `true`                           |
| `AUTO_INDEXER_ENABLED`      | Enable the auto-indexer pipeline (icons and indexing).                                                                   | `true`                           |
| `INDEX_JSON_ENABLED`        | Enable creating/updating `index.json` and `index-cache.json`.                                                            | `false`                          |
| `AUTO_FORMATTER_ENABLED`      | Enable PKG formatting using `AUTO_FORMATTER_TEMPLATE`.                                                                     | `true`                           |
| `AUTO_FORMATTER_MODE`         | Title transform mode for `{title}`: `none`, `uppercase`, `lowercase`, `capitalize`.                                      | `none`                           |
| `AUTO_FORMATTER_TEMPLATE`     | Template using `{title}`, `{titleid}`, `{region}`, `{apptype}`, `{version}`, `{category}`, `{content_id}`, `{app_type}`. | `{title} [{titleid}][{apptype}]` |
| `AUTO_SORTER_ENABLED`        | Enable auto-sorting PKGs into `game/`, `dlc/`, `update/` folders.                                                        | `true`                           |
| `PERIODIC_SCAN_SECONDS`     | Interval in seconds for periodic PKG scans (no inotify watcher).                                                        | `30`                             |
| `CDN_DATA_DIR`              | Host path mapped to `/data`.                                                                                             | `./data`                         |

Dependencies and behavior:

- `PKG_WATCHER_ENABLED=false` disables all automations (format, move, index) and the watcher does not start.
- `AUTO_FORMATTER_TEMPLATE` and `AUTO_FORMATTER_MODE` only apply when `AUTO_FORMATTER_ENABLED=true` and the watcher is enabled.
- Conflicting files are moved to `_errors/`.

## Modules

### Watcher

- Location: `src/modules/watcher/watcher.py`
- Runs periodic scans under `pkg/`.
- Runs a per-file pipeline (formatter → sorter → indexer).

### Auto Formatter

- Location: `modules/auto_formatter/auto_formatter.py`
- Renames PKGs based on `AUTO_FORMATTER_TEMPLATE` and `AUTO_FORMATTER_MODE`.
- Moves conflicts to `_errors/`.

### Auto Sorter

- Location: `modules/auto_sorter/auto_sorter.py`
- Sorts PKGs into `game/`, `dlc/`, `update/` based on SFO metadata.
- Moves conflicts to `_errors/`.

### Auto Indexer

- Location: `modules/auto_indexer/auto_indexer.py`
- Builds `index.json` and `_cache/index-cache.json` from scanned PKGs.
- Only logs when content changes (or icons are extracted).
- Uses `_cache/index-cache.json` to skip reprocessing unchanged PKGs.
- Icon extraction runs per-file in the same pipeline as formatter/sorter.

### PKG Utilities

- Location: `utils/pkg_utils.py`
- Uses `pkgtool` to read SFO metadata and extract icons.

### Log Utilities

- Location: `src/utils/log_utils.py`
- Modular tagging and log level filtering.
- Provides a centralized `log` function.

**Logging Examples:**

```python
from src.utils import log

# Watcher
log("info", "Starting periodic scan", module="WATCHER")

# Auto Formatter
log("info", "Renaming file", message="old.pkg -> NEW.pkg", module="AUTO_FORMATTER")
log("error", "Failed to rename", message="Permission denied", module="AUTO_FORMATTER")

# Auto Sorter
log("info", "Moving PKG to category folder", message="game/my_game.pkg", module="AUTO_SORTER")
log("warn", "Category mapping missing", module="AUTO_SORTER")

# Auto Indexer
log("info", "Indexing started", module="AUTO_INDEXER")
```

Output format: `<timestamp UTC> | [MODULE] Action: Message` (with module-specific colors).

**Colors:**
- `AUTO_INDEXER`: Green
- `AUTO_SORTER`: Yellow
- `AUTO_FORMATTER`: Blue
- `WATCHER`: White

**Level Colors:**
- `DEBUG`: Gray
- `INFO`: White
- `WARN`: Orange
- `ERROR`: Red

Example: `2024-05-20 14:30:05 UTC | [WATCHER] Starting periodic scan` (where `[WATCHER]` is white and the message is white).

### PKG Tool Wrapper

- Location: `tools/pkg_tool.py`
- Wraps the `pkgtool` binary calls used by the indexer.

## Flow diagram (ASCII)

```
periodic scan
                |
                v
           [watcher.py]
                |
                v
   per-file pipeline (sharded)
                |
                v
        [auto_formatter/formatter.py]
                |
          (conflict?)----yes----> /data/_errors
                |
               no
                v
          [auto_sorter/sorter.py]
                |
          (conflict?)----yes----> /data/_errors
                |
               no
                v
     [auto_indexer.py]
                |
                v
           index.json
                |
                v
       _cache/index-cache.json
```

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

- If the index is not updating, remove `/data/_cache/index-cache.json` to force a rebuild.
- If a PKG is encrypted, `pkgtool` may fail to read `param.sfo` and the PKG is moved to `_errors/`.
- If icons are missing, ensure the PKG contains `ICON0_PNG` or `PIC0_PNG`.
- If a format or move conflict is detected, the PKG is moved to `/data/_errors`.
- Files in `_errors/` are not indexed.
- Resolve conflicts manually and move the file back into `pkg/`.
- PKG metadata errors are logged with a human-friendly stage (e.g. `Reading PKG entries`, `PARAM.SFO not found`).
- Each error move appends the full console-formatted line to `/data/_errors/error_log.txt`.
