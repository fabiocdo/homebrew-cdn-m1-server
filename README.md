# hb-store-m1

### Local CDN for PS4 homebrew PKG files using Docker Compose + Nginx with automatic formatting, sorting, icon extraction, and index/database generation.

![512.png](assets/512.png)

## Overview

- Serves `.pkg` files over HTTP with range requests.
- Extracts `ICON0_PNG` to `pkg/_media` for cover images.
- Formats PKG filenames and sorts them into app-type folders.
- Generates `index.json` (Homebrew Store) and `store.db` (fPKGi) when enabled.
- Uses a cache (`_cache/index-cache.json`) to skip reprocessing unchanged files.

## Quick start

The image bundles the watcher/indexer and nginx inside a single container. Run `docker compose up --build` from the repo
root: Docker Compose creates `./configs`/`./data` for you, mounts `./configs` read-write into `/app/configs`, and the
entrypoint generates `configs/settings.env` plus `configs/certs/` (if they don’t already exist). After the first run you
only need to edit `configs/settings.env` to customize `SERVER_IP`, `SERVER_PORT`, the TLS toggle (`ENABLE_TLS`), or any
optional `WATCHER_*` / `AUTO_INDEXER_*` overrides. When HTTPS is enabled, drop `tls.crt`/`tls.key` into
`./configs/certs/` and restart; those files already live under `/app/configs/certs/` inside the container, which is
where the entrypoint looks for them when scaffolding `servers.conf`. `SERVER_IP`, `SERVER_PORT`, and the TLS toggle (
`ENABLE_TLS`) also control the `SERVER_URL` the indexer embeds in each entry, so make sure they match how clients reach
the service.

Mount your PKG directory and caches at `./data` so the watcher and nginx can share `/app/data`.

### Docker run

```bash
docker run -d \
  --name hb-store-m1 \
  -p 80:80 \
  -p 443:443 \
  -v ./data:/app/data \
  -v ./configs:/app/configs \
  fabiocdo/hb-store-m1:latest
```

### Docker Compose

```yaml
version: "3.9"
services:
  hb-store-m1:
    build: .
    image: fabiocdo/hb-store-m1:latest
    container_name: hb-store-m1
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./data:/app/data
      - ./configs:/app/configs
    restart: unless-stopped
```

## Environment variables

| Variable                        | Description                                                                                   | Default     |
|---------------------------------|-----------------------------------------------------------------------------------------------|-------------|
| `SERVER_IP`                     | Host used to build URLs in the index. Scheme is derived from the TLS toggle (`ENABLE_TLS`).   | `127.0.0.1` |
| `SERVER_PORT`                   | Port used to build URLs in the index. Scheme is derived from the TLS toggle (`ENABLE_TLS`).   | `80`        |
| `LOG_LEVEL`                     | Log verbosity: `debug`, `info`, `warn`, `error`.                                              | `info`      |
| `ENABLE_TLS`                    | Serve Nginx via TLS/HTTPS when `true`; otherwise HTTP only. Controls the `SERVER_URL` scheme. | `false`     |
| `WATCHER_ENABLED`               | Master switch for watcher-driven automation.                                                  | `true`      |
| `WATCHER_PERIODIC_SCAN_SECONDS` | Periodic scan interval in seconds.                                                            | `30`        |
| `FPGKI_FORMAT_ENABLED`          | Enable FPKGI format output.                                                                   | `false`     |

Notes:

- The runtime sources `configs/settings.env` before starting the watcher, so updating that file is all you need to tweak
  `SERVER_*`, the TLS toggle (`ENABLE_TLS`), `LOG_LEVEL`, or watcher/index behavior; you can still layer extra `-e` /
  `--env-file` overrides when you run the container.
- `WATCHER_ENABLED=false` stops all automation.
- Store DB is always updated.
- When `ENABLE_TLS=true`, drop TLS certificates under `configs/certs/` so the entrypoint can configure HTTPS.
- `SERVER_IP` should be just the host (or host:port) without `http://` or `https://`.
- Ensure `SERVER_IP` matches the host/port used by clients, and toggle `ENABLE_TLS` to select TLS vs HTTP.
- Data paths are fixed to `/app/data` inside the container.
- Conflicts are moved to `/app/data/_error/` with a reason appended to `/app/data/_logs/errors.log`.
- If `configs/settings.env` is absent, the entrypoint writes a minimal template before continuing; edit that file (or
  replace it with your own) whenever you want to customize the defaults.
- TLS certificates must be placed as `configs/certs/tls.crt` and `configs/certs/tls.key` when `ENABLE_TLS=true`.

## Volumes

| Volume                   | Description                                                                                                              | Default     |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------|-------------|
| `./data:/app/data`       | PKG tree, caches, logs, and generated indexes served by both the watcher and nginx.                                      | `./data`    |
| `./configs:/app/configs` | Configuration directory containing `settings.env` (auto-generated on first run) and TLS material under `configs/certs/`. | `./configs` |

## Data layout

The `/app/data` volume follows this layout:

```
/app/data
|-- pkg/
|   |-- game/
|   |-- update/
|   |-- dlc/
|   |-- save/
|   |-- unknown/
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
- `index.json` is written when enabled by a future toggle (not implemented yet).
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
    "http://localhost:8080/pkg/game/Example%20Game%20%5BCUSA12345%5D.pkg": {
      "region": "USA",
      "name": "Example Game",
      "version": "01.00",
      "release": "01-13-2023",
      "size": 123456789,
      "min_fw": null,
      "cover_url": "http://localhost:8080/pkg/_media/UP0000-CUSA12345_00-EXAMPLE.png"
    }
  }
}
```

## Modules

### Watcher (`src/modules/watcher.py`)

- Periodically scans `pkg/` and orchestrates the pipeline.
- Uses `WATCHER_PERIODIC_SCAN_SECONDS` for the scan interval.
- Skips execution when the cache detects no changes.
- Downloads missing HB-Store update assets into `/app/data/_cache/`.

### Auto Formatter (`src/modules/auto_formatter.py`)

- Renames PKGs to `{CONTENT_ID}.pkg`.
- Moves conflicts to `_error/` and logs a reason.

### Auto Sorter (`src/modules/auto_sorter.py`)

- Moves PKGs into `game/`, `dlc/`, `update/`, `save/`, or `unknown/` based on `app_type`.
- Moves conflicts to `_error/`.

### Auto Indexer (`src/modules/auto_indexer.py`)

- Writes `index.json` and updates `store.db` based on the current plan.
- Builds URLs using `SERVER_IP` and the TLS toggle (`ENABLE_TLS`) and percent-encodes path segments.

## Helpers

### WatcherPlanner (`src/modules/helpers/watcher_planner.py`)

- Scans PKGs via `pkg_scanner` and determines planned actions.
- Marks each PKG/icon as `allow`, `reject`, or `skip`.
- Prevents duplicating planned paths and duplicate icon extraction.

### WatcherExecutor (`src/modules/helpers/watcher_executor.py`)

- Executes the plan in order: move errors, extract icons, rename/sort PKGs.
- Appends reasons to `/app/data/_logs/errors.log` when rejecting.
- Returns execution stats (moves, renames, extractions, errors, skipped).

## Utils

### PkgUtils (`src/utils/pkg_utils.py`)

- Reads `PARAM.SFO` using `pkgtool`.
- Normalizes fields and derives `release_date`, `region`, and `app_type`.
- Extracts `ICON0_PNG` to `pkg/_media` (dry-run supported).

### PkgScanner (`src/utils/pkg_scanner.py`)

- Scans the PKG tree and detects changes using size/mtime/hash.
- Reuses cached SFO data when files are unchanged.
- Marks changes when `SERVER_IP` or the TLS toggle (`ENABLE_TLS`) changes (index URLs must update).

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
- Duplicate planned names or existing target paths → PKG moved to `_error/`.
- Missing or invalid `ICON0_PNG` -> PKG moved to `_error/`.
- If a PKG is already in the correct folder and name, it is marked `skip`.
- If `SERVER_IP` or the TLS toggle (`ENABLE_TLS`) changes, the index is regenerated even when PKGs are unchanged.
- Encrypted PKGs may cause `pkgtool` to fail; these are moved to `_error/`.
- Icons are only extracted when needed (non-existent and not duplicated by another plan item).
- Extracted icons are optimized with `optipng` when available (lossless).

## Nginx behavior

- Serves `/app/data` directly and supports HTTP range requests for `.pkg`.
- `index.json` and `store.db` are served with `no-store` to avoid stale caches.
- Images and PKGs use long-lived cache headers.
- Access logs are written to `/app/data/_logs/access.log` (tail with `tail -f`).
- Update endpoints are served from `/app/data/_cache/`:
    - `/update/remote.md5`
    - `/update/homebrew.elf`
    - `/update/homebrew.elf.sig`
    - `/update/store.prx`
    - `/update/store.prx.sig`
- `/api.php?db_check_hash=true` returns `/app/data/_cache/store.db.json`.

## Troubleshooting

- If the index is not updating, delete `/app/data/_cache/index-cache.json` to force a rebuild.
- If files are stuck in `_error/`, check `/app/data/_logs/errors.log` for the reason.
- Ensure `SERVER_IP` matches the host and port used by clients.
