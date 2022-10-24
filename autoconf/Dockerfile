FROM python:3.11-rc-alpine

# Copy python requirements
COPY bw/deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install dependencies
RUN apk add --no-cache --virtual build g++ gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    mkdir /opt/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
    apk del build

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY autoconf /opt/bunkerweb/autoconf
COPY bw/api /opt/bunkerweb/api
COPY bw/cli /opt/bunkerweb/cli
COPY bw/confs /opt/bunkerweb/confs
COPY bw/core /opt/bunkerweb/core
COPY bw/gen /opt/bunkerweb/gen
COPY bw/helpers /opt/bunkerweb/helpers
COPY bw/settings.json /opt/bunkerweb/settings.json
COPY db /opt/bunkerweb/db
COPY utils /opt/bunkerweb/utils
COPY VERSION /opt/bunkerweb/VERSION

# Add nginx user, drop bwcli, setup data folders, permissions and logging
RUN apk add --no-cache bash git && \
    ln -s /usr/local/bin/python3 /usr/bin/python3 && \
    addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
    apk add --no-cache bash && \
    cp /opt/bunkerweb/helpers/bwcli /usr/local/bin && \
    for dir in $(echo "cache configs configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs cache/letsencrypt plugins www") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
    mkdir /opt/bunkerweb/tmp && \
    chown -R root:nginx /opt/bunkerweb && \
    find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
    chown -R nginx:nginx /data && \
    chmod 770 /opt/bunkerweb/tmp && \
    chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/cli/main.py /usr/local/bin/bwcli /opt/bunkerweb/helpers/*.sh /opt/bunkerweb/autoconf/main.py /opt/bunkerweb/deps/python/bin/* && \
    chown root:nginx /usr/local/bin/bwcli && \
    mkdir /etc/nginx && \
    chown -R nginx:nginx /etc/nginx && \
    chmod -R 770 /etc/nginx

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1"

VOLUME /data /etc/nginx

WORKDIR /opt/bunkerweb/autoconf

USER root:nginx

CMD ["python", "/opt/bunkerweb/autoconf/main.py"]
