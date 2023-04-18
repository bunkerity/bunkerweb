FROM python:3.11.3-alpine

# Copy python requirements
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.1

RUN mkdir -p /usr/share/bunkerweb/deps && \
    cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 > /usr/share/bunkerweb/deps/requirements.txt && \
    rm -rf /tmp/req

# Install dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev && \
    pip install --no-cache-dir --upgrade pip && \
    pip install wheel && \
    mkdir -p /usr/share/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt && \
    apk del .build-deps

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/autoconf /usr/share/bunkerweb/autoconf
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/cli /usr/share/bunkerweb/cli
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils

# Add nginx user, drop bwcli, setup data folders, permissions and logging
RUN apk add --no-cache bash && \
    addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
    cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
    mkdir -p /var/tmp/bunkerweb && \
    mkdir -p /var/www && \
    mkdir -p /etc/bunkerweb && \
    mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
    mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
    mkdir -p /data/cache/letsencrypt && ln -s /data/cache/letsencrypt /etc/letsencrypt && \
    mkdir -p /data/www && ln -s /data/www /var/www/html && \
    for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
    for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
    chown -R root:nginx /data && \
    chmod -R 770 /data && \
    chown -R root:nginx /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb && \
    find /usr/share/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /usr/share/bunkerweb -type d -exec chmod 0750 {} \; && \
    chmod -R 770 /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb && \
    chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/helpers/*.sh /usr/bin/bwcli /usr/share/bunkerweb/autoconf/main.py /usr/share/bunkerweb/deps/python/bin/* && \
    chown root:nginx /usr/bin/bwcli && \
    mkdir /var/log/letsencrypt /var/lib/letsencrypt && \
    chown root:nginx /var/log/letsencrypt /var/lib/letsencrypt && \
    chmod 770 /var/log/letsencrypt /var/lib/letsencrypt

# Fix CVEs
RUN apk add "libcrypto3>=3.0.8-r2" "libssl3>=3.0.8-r2"

VOLUME /data /etc/nginx

WORKDIR /usr/share/bunkerweb/autoconf

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

CMD ["python3", "/usr/share/bunkerweb/autoconf/main.py"]
