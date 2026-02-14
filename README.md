# hb-store-m1

Local CDN for PS4 Homebrew PKGs, with automatic organization, media extraction, SQLite indexing (`store.db`), and optional fPKGi JSON output.

![hb-store-m1](assets/512.png)

## Overview

The service runs in a single container with two processes:

- `nginx` serving files from `/app/data`
- `python -u -m hb_store_m1` running the watcher in the background

Main pipeline:

1. Initialize directories, database, and base assets.
2. Detect PKG/PNG changes via cache (`store-cache.json`).
3. Validate PKG, extract `PARAM.SFO` and media (`ICON0/PIC0/PIC1`).
4. Move/rename to canonical destination using `content_id`.
5. Update `store.db` and optional `*.json` files by app type.

## Runtime Architecture

```mermaid
flowchart TD
    A[Container start] --> B[/entrypoint.sh/]
    B --> C[Load configs/settings.env]
    B --> D[Generate /etc/nginx/conf.d/servers.conf]
    B --> E[nginx -t]
    B --> F[python -u -m hb_store_m1]
    B --> G[nginx -g daemon off]

    F --> H[InitUtils.init_all]
    H --> H1[init_directories]
    H --> H2[init_db]
    H --> H3[init_assets]

    F --> I[Watcher loop]
    I --> J[CacheUtils.compare_pkg_cache]
    J --> K{Changes found?}
    K -->|no| I
    K -->|yes| L[Process changed PKGs]
    L --> M[AutoOrganizer + media extraction]
    M --> N[DBUtils.upsert]
    M --> O[FPKGIUtils.upsert optional]
    N --> P[write store-cache.json]
    O --> P
```

## Current Features

- Serve PKGs with `Accept-Ranges` and long cache headers.
- Organize PKGs by type into:
  - `game`, `dlc`, `update`, `save`, `unknown`
- Rename PKGs to `<CONTENT_ID>.pkg`.
- Extract:
  - `ICON0_PNG` (required)
  - `PIC0_PNG` and `PIC1_PNG` (optional)
- Update `store.db` using `upsert` by `content_id`.
- Generate app-type JSON files when `FPGKI_FORMAT_ENABLED=true`.
- Keep incremental cache in `data/_cache/store-cache.json`.
- Move invalid/conflicting files to `data/_errors`.
- Persist `WARN/ERROR` logs to `data/_logs/app_errors.log`.

## Repository Structure

```text
.
|-- Dockerfile
|-- docker-compose.yml
|-- docker/
|   |-- entrypoint.sh
|   |-- nginx/
|   |   |-- nginx.template.conf
|   |   `-- common.locations.conf
|-- src/hb_store_m1/
|   |-- main.py
|   |-- modules/
|   |   |-- watcher.py
|   |   `-- auto_organizer.py
|   |-- utils/
|   |   |-- init_utils.py
|   |   |-- cache_utils.py
|   |   |-- pkg_utils.py
|   |   |-- db_utils.py
|   |   |-- fpkgi_utils.py
|   |   |-- file_utils.py
|   |   `-- log_utils.py
|   |-- helpers/
|   |   |-- pkgtool.py
|   |   `-- store_assets_client.py
|   `-- models/
|       |-- globals.py
|       `-- ...
|-- init/
|   `-- store_db.sql
`-- tests/
```

## Run with Docker Compose

### 1) Start

```bash
docker compose up --build -d
```

### 2) Follow logs

```bash
docker compose logs -f hb-store-m1
```

### 3) Stop

```bash
docker compose down
```

## Configuration (`configs/settings.env`)

`entrypoint.sh` creates this file automatically on first run.

| Variable | Type | Default in entrypoint | Description |
|---|---|---|---|
| `SERVER_IP` | string | `127.0.0.1` | Host used to build URLs (`SERVER_URL`). |
| `SERVER_PORT` | int | `80` | Nginx port inside container. |
| `ENABLE_TLS` | bool | `false` | `true` requires `configs/certs/tls.crt` and `tls.key`. |
| `LOG_LEVEL` | string | `info` | `debug`, `info`, `warn`, `error`. |
| `WATCHER_ENABLED` | bool | `true` | Enable/disable watcher loop. |
| `WATCHER_PERIODIC_SCAN_SECONDS` | int | `30` | Scan loop interval. |
| `FPGKI_FORMAT_ENABLED` | bool | `false` | Generate/update per-type JSON output (`game.json`, etc.). |

Notes:

- The environment variable name is `FPGKI_FORMAT_ENABLED` (kept as-is in code).
- Python runs with `-u` (unbuffered) in the entrypoint.
- If `ENABLE_TLS=true` and certs are missing, container startup fails.

## Volumes

Current `docker-compose.yml`:

```yaml
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

## Data Layout (`/app/data`)

```text
/app/data
|-- _cache/
|   |-- store-cache.json
|   |-- homebrew.elf
|   |-- homebrew.elf.sig
|   `-- remote.md5
|-- _errors/
|   `-- *.pkg
|-- _logs/
|   `-- app_errors.log
|-- pkg/
|   |-- app/
|   |-- dlc/
|   |-- game/
|   |-- save/
|   |-- update/
|   |-- unknown/
|   `-- _media/
|-- store.db
|-- dlc.json
|-- game.json
|-- save.json
|-- update.json
`-- unknown.json
```

Important notes:

- `store-cache.json` stores metadata (`size|mtime_ns|filename`), not PKG content.
- Cache key is usually `content_id`; if extraction fails, it temporarily falls back to filename stem.
- `data/_errors` receives PKGs that fail validation/conflict/processing rules.

## PKG Processing Flow

```mermaid
sequenceDiagram
    participant W as Watcher
    participant C as CacheUtils
    participant P as PkgUtils
    participant A as AutoOrganizer
    participant D as DBUtils
    participant F as FPKGIUtils

    W->>C: compare_pkg_cache()
    C-->>W: changed sections + current files
    W->>P: validate(pkg)
    alt Status ERROR
        W->>W: move_to_error(validation_failed)
    else Status OK/WARN
        W->>P: extract_pkg_data(pkg)
        W->>A: run(pkg)
        alt organizer failure
            W->>W: move_to_error(organizer_failed)
        else success
            W->>P: extract_pkg_medias(pkg)
            W->>P: build_pkg(...)
            W->>D: upsert(pkgs)
            opt FPGKI_FORMAT_ENABLED=true
                W->>F: upsert(pkgs)
            end
            W->>C: write_pkg_cache()
        end
    end
```

## Type/Region Mapping

From the `PKG` model:

- Category -> app type:
  - `AC` -> `dlc`
  - `GC`/`GD` -> `game`
  - `GP` -> `update`
  - `SD` -> `save`
  - others -> `unknown`
- `content_id` prefix -> region:
  - `UP` USA, `EP` EUR, `JP` JAP, `HP/AP/KP` ASIA, others `UNKNOWN`

## Exposed HTTP Endpoints (nginx)

| Endpoint | Source | Behavior |
|---|---|---|
| `/` | redirect | `302` to `/store.db` |
| `/store.db` | `/app/data/store.db` | `no-store`, byte-range enabled |
| `/api.php` | `/app/data/_cache/store.db.json` | serves JSON if file exists |
| `/update/remote.md5` | `/_cache/remote.md5` | `no-store` |
| `/update/homebrew.elf` | `/_cache/homebrew.elf` | `no-store` |
| `/update/homebrew.elf.sig` | `/_cache/homebrew.elf.sig` | `no-store` |
| `/update/store.prx` | `/_cache/store.prx` | `no-store` |
| `/update/store.prx.sig` | `/_cache/store.prx.sig` | `no-store` |
| `/pkg/**/*.pkg` | `/app/data/pkg` | long cache (`max-age=31536000`, `immutable`), range |
| `/pkg/**/*.(png|jpg|jpeg|webp)` | `/app/data/pkg` | 30-day cache |
| `/pkg/**/*.(json|db)` | `/app/data/pkg` | `no-store` |

## CI/CD (GitLab)

Current pipeline (`.gitlab-ci.yml`):

1. `test`
   - runs `pytest` with coverage
   - gate: `--cov-fail-under=90`
   - publishes `coverage.xml`

2. `mirror_to_github`
   - runs on `push` to `main`
   - executes `git push --mirror` to GitHub
   - required variables:
     - `GITHUB_MIRROR_REPO` (`owner/repo`)
     - `GITHUB_MIRROR_USER`
     - `GITHUB_MIRROR_TOKEN`

3. `build`
   - builds Docker image tagged with commit SHA
   - exports `image.tar` artifact

4. `publish:*` (manual)
   - `publish:release`, `publish:stable`, `publish:dev`
   - tag derived from `version` in `pyproject.toml`
   - required variables:
     - `DOCKER_HUB_USER`
     - `DOCKER_HUB_TOKEN`

## Local Development (without Docker)

Requirements:

- Python 3.12+
- working `bin/pkgtool`
- native runtime libraries required by `pkgtool`

Run:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
python -m hb_store_m1
```

Tests:

```bash
.venv/bin/pytest -q
.venv/bin/pytest --cov=hb_store_m1 --cov-report=term-missing --cov-fail-under=90
```

## Troubleshooting

### `docker compose up` does not start the service

- Check:
  - `docker compose logs hb-store-m1`
  - `nginx -t` output (already executed by entrypoint)
- Common cause: `ENABLE_TLS=true` without `configs/certs/tls.crt` and `tls.key`.

### Valid PKG moved to `_errors`

- Check `data/_logs/app_errors.log`.
- Common reasons:
  - critical validation failure
  - `PARAM.SFO` extraction failure
  - missing `ICON0_PNG`
  - destination conflict (`content_id.pkg` already exists)

### `No usable version of libssl was found`

- This means a native dependency required by `pkgtool` is missing.
- Current Dockerfile already copies `libssl.so.1.1` and `libcrypto.so.1.1` from toolchain.

### App version in banner did not update

Rebuild and restart:

```bash
docker compose up --build -d
```

The app reads version from `pyproject.toml` when available, with fallback to installed package metadata.

## License

Add your project license here (for example: MIT, GPL-3.0).
