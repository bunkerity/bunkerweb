FROM python:3.10-alpine AS builder

# Copy python requirements
COPY deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    mkdir /opt/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
    apk del build

FROM python:3.10-alpine

COPY --from=builder /opt/bunkerweb/deps/python /opt/bunkerweb/deps/python

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY api /opt/bunkerweb/api
COPY confs /opt/bunkerweb/confs
COPY core /opt/bunkerweb/core
COPY gen /opt/bunkerweb/gen
COPY utils /opt/bunkerweb/utils
COPY settings.json /opt/bunkerweb/settings.json
COPY VERSION /opt/bunkerweb/VERSION
COPY ui/requirements.txt /opt/bunkerweb/ui/requirements.txt

# Install UI requirements
RUN apk add --no-cache --virtual build gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    pip install -r /opt/bunkerweb/ui/requirements.txt && \
    apk del build

COPY ui /opt/bunkerweb/ui

# Add nginx user
RUN addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
    apk add --no-cache bash file && \
    for dir in $(echo "cache configs letsencrypt plugins www") ; do ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
    mkdir /opt/bunkerweb/tmp && \
    chown -R root:nginx /opt/bunkerweb && \
    find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
    chmod 770 /opt/bunkerweb/tmp && \
    chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/deps/python/bin/* && \  
    mkdir /etc/nginx && \
    chown -R nginx:nginx /etc/nginx && \
    chmod -R 770 /etc/nginx && \
    ln -s /usr/local/bin/python /usr/bin/python3

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1" "expat>=2.5.0-r0" "krb5-libs>=1.19.4-r0" "libcurl>=7.87.0-r2"

VOLUME /data /etc/nginx

EXPOSE 7000

WORKDIR /opt/bunkerweb/ui
USER nginx:nginx

CMD ["gunicorn", "--bind=0.0.0.0:7000", "--workers=1", "--threads=2", "main:app"]
