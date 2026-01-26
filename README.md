# homebrew-store-cdn

Local CDN with Docker Compose and Nginx in front of a static origin.

## Usage

Set the variables in `.env`:

- `BASE_URL`: URL used in `index.json`
- `CDN_DATA_DIR`: host path for data
- `GENERATE_JSON_PERIOD`: delay before regenerating `index.json` after file changes

Start the container:

```bash
docker compose up -d
```

Access:

- http://localhost:8080

## Examples

Sample `.env`:

```
BASE_URL=http://192.168.0.10:8080
CDN_DATA_DIR=/home/fabio/ps4
GENERATE_JSON_PERIOD=5
```

Example host data layout:

```
/home/fabio/ps4/
|-- pkg/
|   |-- game/
|   |   |-- MAGICKA 2 [CUSA02421].pkg
|   |-- update/
|   |   |-- MAGICKA 2 [Patch] [CUSA02421].pkg
|   |-- dlc/
|   |   |-- Corneo Armlet [Addon] [CUSA07211].pkg
|   |-- app/
|       |-- PS4_PKGI13337_v1.01.1.pkg
|-- _media/
|   |-- CUSA02421.png
|   |-- CUSA07211.png
|   |-- PKGI13337.png
|-- index.json
```

Example `index.json` entry:

```json
{
  "id": "CUSA02421",
  "name": "MAGICKA 2",
  "version": "1.01",
  "apptype": "update",
  "pkg": "http://192.168.0.10:8080/pkg/update/MAGICKA%202%20%5BPatch%5D%20%5BCUSA02421%5D.pkg",
  "icon": "http://192.168.0.10:8080/_media/CUSA02421.png",
  "category": "gp",
  "region": "EUR"
}
```

## Structure

- `pkg/`: `.pkg` packages (mounted at `/data/pkg`)
- `_media/`: images/icons (mounted at `/data/_media`)
- `index.json`: generated index (at `/data/index.json`)
- `nginx.conf`: server configuration
- `docker-compose.yml`: service orchestration

## Host Data Layout

The host directory mapped to `/data` must follow this layout:

```
<CDN_DATA_DIR>/
|-- pkg/ # Put your PKGs here
|   |-- game/   # Auto-created
|   |-- dlc/    # Auto-created
|   |-- update/ # Auto-created
|   |-- app/    # Auto-created (no auto-move)
|   |-- Game Name [CUSA12345].pkg
|-- _media/ # Generated Automatically
|   |-- CUSA12345.png
|-- index.json # Generated Automatically
```

Notes:
- `index.json` and `_media/*.png` are generated automatically.
- Place your `.pkg` files inside `pkg/`.
- The container watches `pkg/` and regenerates `index.json` on changes.

## Notes

- The Nginx cache is stored in a named volume `edge-cache`.
- `X-Cache-Status` header indicates HIT/MISS/BYPASS.
