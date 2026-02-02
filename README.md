# homebrew-store-cdn

Local CDN for PS4 homebrew PKG files using Docker Compose + Nginx, with automatic
formatting, sorting, icon extraction, and index/database generation.

## Overview

- Serves `.pkg` files over HTTP with range requests.
- Extracts `ICON0_PNG` to `pkg/_media` for cover images.
- Formats PKG filenames and sorts them into app-type folders.
- Generates `index.json` (Homebrew Store) and `store.db` (fPKGi) when enabled.
- Uses a cache (`_cache/index-cache.json`) to skip reprocessing unchanged files.

## Quick start

### Docker run

```bash
docker run -d \
  --name homebrew-store-cdn \
  -p 8080:80 \
  -e BASE_URL=http://127.0.0.1:8080 \
  -e LOG_LEVEL=info \
  -e WATCHER_ENABLED=true \
  -e AUTO_INDEXER_OUTPUT_FORMAT=db,json \
  -e AUTO_FORMATTER_MODE=snake_uppercase \
  -e AUTO_FORMATTER_TEMPLATE="{title}_[{region}]_[{app_type}]_[{version}]" \
  -e WATCHER_PERIODIC_SCAN_SECONDS=30 \
  -v ./data:/data \
  -v ./nginx.conf:/etc/nginx/nginx.conf:ro \
  fabiocdo/homebrew-store-cdn:latest
```

### Docker Compose

```yaml
services:
  homebrew-store-cdn:
    image: fabiocdo/homebrew-store-cdn:latest
    container_name: homebrew-store-cdn
    ports:
      - "8080:80"
    env_file:
      - ./settings.env
    volumes:
      - ./data:/data
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    restart: unless-stopped
```

### Local (Python)

```bash
# default settings.env
python3 -m src

# custom settings file
python3 -m src -E local
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `BASE_URL` | Base URL used to build `pkg` and `cover_url` in the index. | `http://127.0.0.1:8080` |
| `LOG_LEVEL` | Log verbosity: `debug`, `info`, `warn`, `error`. | `info` |
| `WATCHER_ENABLED` | Master switch for watcher-driven automation. | `true` |
| `WATCHER_PERIODIC_SCAN_SECONDS` | Periodic scan interval in seconds. | `30` |
| `WATCHER_SCAN_BATCH_SIZE` | Batch size for PKG scanning (use a large value to effectively disable batching). | `50` |
| `WATCHER_ACCESS_LOG_TAIL` | Enable tailing Nginx access log from watcher. | `true` |
| `WATCHER_ACCESS_LOG_INTERVAL` | Tail interval in seconds. | `5` |
| `AUTO_INDEXER_OUTPUT_FORMAT` | Output targets: `DB`, `JSON` (comma-separated). | `db,json` |
| `AUTO_FORMATTER_MODE` | Title mode: `none`, `uppercase`, `lowercase`, `capitalize`, `snake_uppercase`, `snake_lowercase`. | `snake_uppercase` |
| `AUTO_FORMATTER_TEMPLATE` | Template using `{title}`, `{title_id}`, `{content_id}`, `{category}`, `{version}`, `{release_date}`, `{region}`, `{app_type}`. | `{title}_[{region}]_[{app_type}]_[{version}]` |

Notes:

- `WATCHER_ENABLED=false` stops all automation.
- `AUTO_INDEXER_OUTPUT_FORMAT` controls output: include `JSON` to write `index.json`, include `DB` to update `store.db`.
- Data paths are fixed to `/data` inside the container.
- Conflicts are moved to `/data/_error/` with a reason appended to `/data/_logs/errors.log`.
- Access log tailing writes lines as `WATCHER` debug logs.

## Volumes

| Volume | Description | Default |
|---|---|---|
| `./data:/data` | Host data directory mapped to `/data`. | `./data` |
| `./nginx.conf:/etc/nginx/nginx.conf:ro` | Custom Nginx config (optional). | `./nginx.conf` |

## Data layout

The `/data` volume follows this layout:

```
/data
|-- pkg/
|   |-- game/
|   |-- update/
|   |-- dlc/
|   |-- save/
|   |-- _unknown/
|   |-- _media/          # extracted icons
|   |-- _PUT_YOUR_PKGS_HERE
|   |-- *.pkg
|-- _cache/
|   |-- index-cache.json
|   |-- remote.md5
|   |-- store.db.md5
|   |-- store.db.json
|   |-- homebrew.elf
|   |-- homebrew.elf.sig
|   |-- store.prx
|   |-- store.prx.sig
|-- _error/
|-- _logs/
|   |-- errors.log
|-- index.json
|-- store.db
```

Notes:

- PKGs placed in `pkg/` are formatted and sorted, but only indexed once under a category folder.
- Files under `_error/` are not indexed.
- `index.json` is written only when `AUTO_INDEXER_OUTPUT_FORMAT` includes `JSON`.
- Update assets are downloaded from the official PS4-Store releases if missing:
  - Required: `homebrew.elf`, `homebrew.elf.sig`, `remote.md5`
  - Optional (if present in the release): `store.prx`, `store.prx.sig`
- `store.db.md5` (plain hash) and `store.db.json` (JSON with `hash`) are generated from `store.db`
  and used by `/api.php?db_check_hash=true`.

## index.json format

Example payload:

```json
{
  "DATA": {
    "http://127.0.0.1:8080/pkg/game/Example%20Game%20%5BCUSA12345%5D.pkg": {
      "region": "USA",
      "name": "Example Game",
      "version": "01.00",
      "release": "01-13-2023",
      "size": 123456789,
      "min_fw": null,
      "cover_url": "http://127.0.0.1:8080/pkg/_media/UP0000-CUSA12345_00-EXAMPLE.png"
    }
  }
}
```

## Modules

### Watcher (`src/modules/watcher.py`)

- Periodically scans `pkg/` and orchestrates the pipeline.
- Uses `WATCHER_PERIODIC_SCAN_SECONDS` for the scan interval.
- Skips execution when cache detects no changes.
- When `WATCHER_ACCESS_LOG_TAIL=true`, tails `/data/_logs/access.log` in a background thread.
- Downloads missing HB-Store update assets into `/data/_cache/`.

### Auto Formatter (`src/modules/auto_formatter.py`)

- Builds filenames from `AUTO_FORMATTER_TEMPLATE`.
- Applies title transformations with `AUTO_FORMATTER_MODE`.
- Moves conflicts to `_error/` and logs a reason.

### Auto Sorter (`src/modules/auto_sorter.py`)

- Moves PKGs into `game/`, `dlc/`, `update/`, `save/`, or `_unknown/` based on `app_type`.
- Moves conflicts to `_error/`.

### Auto Indexer (`src/modules/auto_indexer.py`)

- Writes `index.json` and updates `store.db` based on the current plan.
- Uses `AUTO_INDEXER_OUTPUT_FORMAT` to decide which outputs to write.
- Builds URLs using `BASE_URL` and percent-encodes path segments.

## Helpers

### WatcherPlanner (`src/modules/helpers/watcher_planner.py`)

- Scans PKGs via `pkg_scanner` and determines planned actions.
- Marks each PKG/icon as `allow`, `reject`, or `skip`.
- Prevents duplicate planned paths and duplicate icon extraction.

### WatcherExecutor (`src/modules/helpers/watcher_executor.py`)

- Executes the plan in order: move errors, extract icons, rename/sort PKGs.
- Appends reasons to `/data/_logs/errors.log` when rejecting.
- Returns execution stats (moves, renames, extractions, errors, skipped).

## Utils

### PkgUtils (`src/utils/pkg_utils.py`)

- Reads `PARAM.SFO` using `pkgtool`.
- Normalizes fields and derives `release_date`, `region`, and `app_type`.
- Extracts `ICON0_PNG` to `pkg/_media` (dry-run supported).

### PkgScanner (`src/utils/pkg_scanner.py`)

- Scans the PKG tree and detects changes using size/mtime/hash.
- Reuses cached SFO data when files are unchanged.
- Marks changes when `BASE_URL` changes (index URLs must update).

### IndexCache (`src/utils/index_cache.py`)

- Loads/saves `index-cache.json` in `_cache/`.
- Stores file metadata, SFO payloads, and last generated index entries.

### Log Utils (`src/utils/log_utils.py`)

- Centralized logging with module tags and level filtering.
- Module color tags: `WATCHER`, `WATCHER_PLANNER`, `WATCHER_EXECUTOR`, `AUTO_FORMATTER`, `AUTO_SORTER`, `AUTO_INDEXER`.

### Utils Models (`src/utils/models/*.py`)

- Defines shared enums and mappings (`REGION_MAP`, `APP_TYPE_MAP`, etc.).

## Flow diagram

```
Watcher.start()
  |
  |-- WatcherPlanner.plan()
  |     |-- pkg_scanner.scan_pkgs()
  |           |-- index_cache.load_cache()
  |           |-- pkg_utils.extract_pkg_data()
  |
  |-- WatcherExecutor.run()
  |     |-- AutoFormatter.run()
  |     |-- AutoSorter.run()
  |     |-- pkg_utils.extract_pkg_icon()
  |
  |-- AutoIndexer.run()
        |-- index_cache.load_cache()/save_cache()
        |-- write index.json / update store.db
```

## Edge cases and behavior

- Missing or unreadable `PARAM.SFO` -> PKG moved to `_error/`.
- Duplicate planned names or existing target paths -> PKG moved to `_error/`.
- Missing or invalid `ICON0_PNG` -> PKG moved to `_error/`.
- If a PKG is already in the correct folder and name, it is marked `skip`.
- If `BASE_URL` changes, the index is regenerated even when PKGs are unchanged.
- Encrypted PKGs may cause `pkgtool` to fail; these are moved to `_error/`.
- Icons are only extracted when needed (non-existent and not duplicated by another plan item).
- Extracted icons are optimized with `optipng` when available (lossless).

## Nginx behavior

- Serves `/data` directly and supports HTTP range requests for `.pkg`.
- `index.json` and `store.db` are served with `no-store` to avoid stale caches.
- Images and PKGs use long-lived cache headers.
- Access logs are written to `/data/_logs/access.log` (tail with `tail -f`).
- Update endpoints are served from `/data/_cache/`:
  - `/update/remote.md5`
  - `/update/homebrew.elf`
  - `/update/homebrew.elf.sig`
  - `/update/store.prx`
  - `/update/store.prx.sig`
- `/api.php?db_check_hash=true` returns `/data/_cache/store.db.json`.

## Troubleshooting

- If the index is not updating, delete `/data/_cache/index-cache.json` to force a rebuild.
- If files are stuck in `_error/`, check `/data/_logs/errors.log` for the reason.
- Ensure `BASE_URL` matches the host and port used by clients.
