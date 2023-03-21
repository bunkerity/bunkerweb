FROM python:3.11-alpine

# Copy python requirements
COPY src/ui/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
    cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 /tmp/req/requirements.txt.2 > /usr/share/bunkerweb/deps/requirements.txt && \
    rm -rf /tmp/req

# Install python requirements
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev && \
    pip install --no-cache-dir --upgrade pip && \
    pip install wheel && \
    mkdir -p /usr/share/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt && \
    apk del .build-deps

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/ui /usr/share/bunkerweb/ui
COPY src/VERSION /usr/share/bunkerweb/VERSION

# Add ui user
RUN apk add --no-cache bash && \
    addgroup -g 101 ui && \
    adduser -h /var/cache/nginx -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
    echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
    mkdir -p /var/tmp/bunkerweb && \
    mkdir -p /etc/bunkerweb && \
    mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
    mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
    mkdir -p /var/log/nginx/ && touch /var/log/nginx/ui.log && \
    for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
    for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
    chown -R root:ui /data && \
    chmod -R 770 /data && \
    chown -R root:ui /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/log/nginx && \
    for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type f -exec chmod 0740 {} \; ; done && \
    for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type d -exec chmod 0750 {} \; ; done && \
    chmod 770 /var/cache/bunkerweb /var/lib/bunkerweb /var/tmp/bunkerweb /var/log/nginx/ui.log && \
    chmod 750 /usr/share/bunkerweb/gen/*.py /usr/share/bunkerweb/deps/python/bin/* && \
    chmod 660 /usr/share/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "libxml2>=2.9.14-r1" "expat>=2.5.0-r0" "git>=2.36.5-r0" "curl>=7.87.0-r2" "libcurl>=7.87.0-r2" "libcom_err>=1.46.6-r0"

VOLUME /data /etc/nginx

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

ENV PYTHONPATH /usr/share/bunkerweb/deps/python
CMD ["python3", "-m", "gunicorn", "--access-logfile=-", "--graceful-timeout=0", "--bind=0.0.0.0:7000", "--workers=1", "--threads=2", "--user", "ui", "--group", "ui", "main:app"]