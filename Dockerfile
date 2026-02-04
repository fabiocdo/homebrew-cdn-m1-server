# Stage 1: Orbis Toolchain
FROM openorbisofficial/toolchain:latest AS toolchain

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    nginx \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir requests

WORKDIR /app
COPY src/ /app

RUN mkdir -p /app/bin
COPY --from=toolchain /lib/OpenOrbisSDK/bin/linux/PkgTool.Core /app/bin/pkgtool
RUN chmod +x /app/bin/pkgtool

# Bake nginx base config + locations
COPY docker/nginx/nginx.template.conf /etc/nginx/nginx.conf
COPY docker/nginx/common.locations.conf /etc/nginx/templates/common.locations.conf

# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && mkdir -p /app/data /var/log/nginx /tmp/nginx \
 && mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi \
 && mkdir -p /etc/nginx/conf.d

ENV PYTHONPATH=/app
ENV CONFIG_DIR=/app/configs
EXPOSE 80 443
ENTRYPOINT ["/entrypoint.sh"]
