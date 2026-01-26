# homebrew-store-cdn

Local CDN with Docker Compose and Nginx in front of a static origin.

## Usage

Set the variables in `.env`:

- `BASE_URL`: URL used in `index.json`
- `CDN_DATA_DIR`: host path for data

Start the container:

```bash
docker compose up -d
```

Access:

- http://localhost:8080

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
|   |-- Game Name [CUSA12345].pkg
|-- _media/ # Generated Automatically
|   |-- icons/
|       |-- CUSA12345.png
|-- index.json # Generated Automatically
```

Notes:
- `index.json` and `_media/icons/*.png` are generated automatically.
- Place your `.pkg` files inside `pkg/`.
- The container watches `pkg/` and regenerates `index.json` on changes.

## Notes

- The Nginx cache is stored in a named volume `edge-cache`.
- `X-Cache-Status` header indicates HIT/MISS/BYPASS.
