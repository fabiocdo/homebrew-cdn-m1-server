FROM openorbisofficial/toolchain:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# OpenOrbis image runs as non-root user
USER root

# Install system dependencies
RUN apt update && apt install -y --no-install-recommends \
    nginx \
    inotify-tools \
    python3 \
    python3-pip \
    sqlite3 \
 && rm -rf /var/lib/apt/lists/*

# Use the PkgTool bundled in the official OpenOrbis image
RUN if command -v PkgTool.Core >/dev/null 2>&1; then ln -s "$(command -v PkgTool.Core)" /usr/local/bin/pkgtool; fi

# Install pip globally
RUN python3 -m pip install --upgrade pip setuptools wheel --no-cache-dir \
 && python3 -m pip cache purge

# NGINX configuration
RUN rm /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/nginx.conf

# Copy app files
COPY entrypoint.sh /entrypoint.sh
COPY src/__main__.py settings.py /app/
COPY src/modules/ /app/modules/
COPY src/utils/ /app/utils/
COPY src/tools/ /app/tools/
COPY lib/ /app/lib/
RUN chmod +x /entrypoint.sh

# Data volume
VOLUME ["/data"]

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
