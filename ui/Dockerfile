FROM python:3-alpine AS builder

# Copy python requirements
COPY bw/deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build g++ gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    mkdir /opt/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
    apk del build

FROM python:3-alpine

COPY --from=builder /opt/bunkerweb/deps/python /opt/bunkerweb/deps/python

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY bw/api /opt/bunkerweb/api
COPY bw/confs /opt/bunkerweb/confs
COPY bw/core /opt/bunkerweb/core
COPY bw/gen /opt/bunkerweb/gen
COPY utils /opt/bunkerweb/utils
COPY bw/settings.json /opt/bunkerweb/settings.json
COPY VERSION /opt/bunkerweb/VERSION
COPY ui/requirements.txt /opt/bunkerweb/ui/requirements.txt

# Install UI requirements
RUN apk add --no-cache --virtual build gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    pip install -r /opt/bunkerweb/ui/requirements.txt && \
    apk del build

COPY ui /opt/bunkerweb/ui

# Add ui user
RUN apk add --no-cache bash file && \
    addgroup -g 101 ui && \
    adduser -h /var/cache/nginx -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
    for dir in $(echo "cache configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
    mkdir /opt/bunkerweb/tmp && \
    chown -R root:ui /opt/bunkerweb && \
    find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
    chown -R ui:ui /data && \
    chmod 770 /opt/bunkerweb/tmp && \
    chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/deps/python/bin/* && \  
    mkdir /etc/nginx && \
    chown -R ui:ui /etc/nginx && \
    chmod -R 770 /etc/nginx && \
    ln -s /usr/local/bin/python /usr/bin/python3

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1"

VOLUME /data /etc/nginx

EXPOSE 7000

WORKDIR /opt/bunkerweb/ui

USER ui:ui

CMD ["gunicorn", "--bind=0.0.0.0:7000", "--workers=1", "--threads=2", "main:app"]
