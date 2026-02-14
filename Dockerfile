# syntax=docker/dockerfile:1.7

# Stage 1: Orbis Toolchain
FROM openorbisofficial/toolchain:latest AS toolchain

# Stage 2: Builder (gera wheel)
FROM python:3.12-slim AS builder
WORKDIR /build

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -U pip build
COPY pyproject.toml /build/
COPY src/ /build/src/
RUN python -m build --wheel

# Stage 3: Runtime
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    nginx \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -U pip \
 && python -m pip install /tmp/*.whl \
 && rm -f /tmp/*.whl


ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
ENV PYTHONUNBUFFERED=1
COPY --from=toolchain /lib/OpenOrbisSDK/bin/linux/PkgTool.Core /usr/local/bin/pkgtool
COPY --from=toolchain /usr/lib/x86_64-linux-gnu/libssl.so.1.1 /usr/lib/x86_64-linux-gnu/libssl.so.1.1
COPY --from=toolchain /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1
RUN chmod +x /usr/local/bin/pkgtool
RUN mkdir -p /app/bin && ln -sf /usr/local/bin/pkgtool /app/bin/pkgtool

COPY docker/nginx/nginx.template.conf /etc/nginx/nginx.conf
COPY docker/nginx/common.locations.conf /etc/nginx/templates/common.locations.conf
COPY init/store_db.sql /app/init/store_db.sql

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && mkdir -p /app/data /var/log/nginx /tmp/nginx \
 && mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi \
 && mkdir -p /etc/nginx/conf.d

ENV CONFIG_DIR=/app/configs
EXPOSE 80 443
ENTRYPOINT ["/entrypoint.sh"]
