FROM python:3.11-alpine

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/confs /usr/share/bunkerweb/confs
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/VERSION /usr/share/bunkerweb/VERSION

# Copy python requirements
COPY src/ui/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/ui/deps && \
    cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 /tmp/req/requirements.txt.2 > /usr/share/bunkerweb/ui/deps/requirements.txt && \
    rm -rf /tmp/req

# Install python requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install wheel && \
    mkdir -p /usr/share/bunkerweb/ui/deps/python && \
    pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/ui/deps/python -r /usr/share/bunkerweb/ui/deps/requirements.txt && \
    pip install --no-cache-dir gunicorn

COPY src/ui /usr/share/bunkerweb/ui

# Add ui user
RUN apk add --no-cache bash file && \
    addgroup -g 101 ui && \
    adduser -h /var/cache/nginx -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
    mkdir -p /var/tmp/bunkerweb && \
    mkdir -p /etc/bunkerweb && \
    mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
    for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
    for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
    chown -R root:ui /data && \
    chmod -R 770 /data && \
    chown -R root:ui /usr/share/bunkerweb /var/cache/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb && \
    for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type f -exec chmod 0740 {} \; ; done && \
    for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type d -exec chmod 0750 {} \; ; done && \
    chmod 770 /var/cache/bunkerweb /var/tmp/bunkerweb && \
    chmod 750 /usr/share/bunkerweb/gen/main.py /usr/share/bunkerweb/ui/deps/python/bin/*

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1"

VOLUME /data

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

CMD ["python3", "-m", "gunicorn", "--bind=0.0.0.0:7000", "--workers=1", "--threads=2", "--user", "ui", "--group", "ui", "main:app"]
