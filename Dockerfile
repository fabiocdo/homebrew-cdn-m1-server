FROM openorbisofficial/toolchain:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# OpenOrbis image runs as non-root user
USER root

# Install system dependencies
RUN apt update && apt install -y --no-install-recommends \
    ca-certificates \
    openssl \
    nginx \
    optipng \
    python3 \
    sqlite3 \
 && rm -rf /var/lib/apt/lists/*

# Use the PkgTool bundled in the official OpenOrbis image
RUN mkdir -p /app/bin \
 && if command -v PkgTool.Core >/dev/null 2>&1; then ln -s "$(command -v PkgTool.Core)" /app/bin/pkgtool; fi

# NGINX configuration
RUN rm /etc/nginx/sites-enabled/default
COPY example/nginx.conf example/nginx.http.conf /app/

# Copy app files
COPY entrypoint.sh /entrypoint.sh
COPY example/settings.env /app/settings.env
COPY pyproject.toml /app/
COPY src/ /app/src/
RUN chmod +x /entrypoint.sh

# Default workdir
WORKDIR /app

# Data volume
VOLUME ["/data"]

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
