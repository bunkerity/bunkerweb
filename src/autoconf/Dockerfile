FROM python:3.11-alpine

# Copy python requirements
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.1

RUN mkdir -p /usr/share/bunkerweb/deps && \
    cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 > /usr/share/bunkerweb/deps/requirements.txt && \
    rm -rf /tmp/req

# Install dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc && \
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
    chown -R nginx:nginx /usr/share/bunkerweb && \
    find /usr/share/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /usr/share/bunkerweb -type d -exec chmod 0750 {} \; && \
    chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/helpers/*.sh /usr/bin/bwcli /usr/share/bunkerweb/autoconf/main.py /usr/share/bunkerweb/deps/python/bin/* && \
    chown root:nginx /usr/bin/bwcli

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1"

VOLUME /data /etc/nginx

WORKDIR /usr/share/bunkerweb/autoconf

USER root:nginx

CMD ["python3", "/usr/share/bunkerweb/autoconf/main.py"]
