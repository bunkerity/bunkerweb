FROM python:3.11.4-alpine AS builder

# Copy python requirements
COPY src/ui/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
    cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 /tmp/req/requirements.txt.2 > /usr/share/bunkerweb/deps/requirements.txt && \
    rm -rf /tmp/req

# Install python dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev file make

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
    mkdir -p /usr/share/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt

# Remove build dependencies
RUN apk del .build-deps && \
    rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/ui /usr/share/bunkerweb/ui
COPY src/VERSION /usr/share/bunkerweb/VERSION

FROM python:3.11.4-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Add ui user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash && \
    addgroup -g 101 ui && \
    adduser -h /var/cache/nginx -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
    echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
    mkdir -p /var/tmp/bunkerweb && \
    mkdir -p /var/run/bunkerweb && \
    mkdir -p /etc/bunkerweb && \
    mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
    mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
    mkdir -p /var/log/bunkerweb/ && \
    for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
    for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
    chown -R root:ui /data && \
    chmod -R 770 /data && \
    chown -R root:ui /usr/share/bunkerweb/INTEGRATION /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
    chmod 770 /var/cache/bunkerweb /var/lib/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
    chmod 750 /usr/share/bunkerweb/gen/*.py /usr/share/bunkerweb/ui/*.py /usr/share/bunkerweb/ui/src/*.py /usr/share/bunkerweb/deps/python/bin/* /usr/share/bunkerweb/helpers/*.sh && \
    chmod 660 /usr/share/bunkerweb/INTEGRATION && \
    chown root:ui /usr/share/bunkerweb/INTEGRATION && \
    ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \
    ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

# Fix CVEs
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

VOLUME /data /etc/nginx

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python
CMD ["python3", "-m", "gunicorn", "--config", "/usr/share/bunkerweb/ui/gunicorn.conf.py", "--user", "ui", "--group", "ui", "--bind", "0.0.0.0:7000"]
