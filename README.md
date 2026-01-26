# homebrew-store-cdn

Local CDN for PS4 homebrew packages using Docker Compose and Nginx, with automatic
index generation and icon extraction.

## What it does

- Serves `.pkg` files over HTTP.
- Generates `index.json` for Homebrew Store clients.
- Extracts `icon0.png` from each PKG and serves it from `_media`.
- Organizes PKGs into `game/`, `update/`, `dlc/`, and `app/` folders.
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
-e GENERATE_JSON_PERIOD=2 \
  -v ./data:/data \
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
      - GENERATE_JSON_PERIOD=2
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Run:

```bash
docker compose up -d
```

### Option C: Build locally

1) Edit `.env` (see example folder):

```
BASE_URL=http://<YOUR_SERVER_IP_ADDRESS>
CDN_DATA_DIR=<PATH_TO_HOST_DATA_DIRECTORY>
GENERATE_JSON_PERIOD=2
```

2) Build and run:

```bash
docker compose build
docker compose up -d
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
|-- index.json             # Auto-generated index
```

Notes:
- `index.json` and `_media/*.png` are generated automatically.
- The tool ignores any PKG located inside folders that start with `_`.
- The `_PUT_YOUR_PKGS_HERE` file is a marker created on container startup.
- Auto-created folders and the marker are only created during container startup.

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
- `id`, `name`, `version`: extracted from `param.sfo`, fallback to filename.
- `apptype`: derived from `CATEGORY` or forced to `app` for `pkg/app`.
- `pkg`, `icon`: URLs built from `BASE_URL`.
- `category`: optional, only when present.
- `region`: optional, derived from `CONTENT_ID`.

## Environment variables

| Variable | Description | Default                 |
| --- | --- |-------------------------|
| `BASE_URL` | Base URL written in `index.json`. | `http://127.0.0.1:8080` |
| `CDN_DATA_DIR` | Host path mapped to `/data`. | `./data`                |
| `GENERATE_JSON_PERIOD` | Delay (seconds) before regenerating `index.json` after changes. | `2`                     |

## Nginx behavior

- Serves `/data` directly.
- Adds cache headers for `.pkg`, `.zip`, and image files.
- Supports HTTP range requests for large downloads.

## Troubleshooting

- If a PKG is encrypted, `pkgtool` may fail to read `param.sfo`.
  In that case, the entry still appears in `index.json` using the filename.
- If icons are missing, ensure the PKG contains `ICON0_PNG` or `PIC0_PNG`.
