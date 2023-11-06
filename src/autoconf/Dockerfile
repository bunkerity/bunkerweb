FROM python:3.12.0-alpine3.18@sha256:a5d1738d6abbdff3e81c10b7f86923ebcb340ca536e21e8c5ee7d938d263dba1 AS builder

# Install python dependencies
# RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/autoconf/requirements.txt /tmp/req/requirements.txt

WORKDIR /usr/share/bunkerweb

RUN mkdir -p deps/python && \
  cat /tmp/req/requirements.txt* > deps/requirements.txt && \
  rm -rf /tmp/req

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --ignore-installed --require-hashes -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Remove build dependencies
# RUN apk del .build-deps && \
RUN rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/autoconf autoconf
COPY src/common/api api
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

FROM python:3.12.0-alpine3.18@sha256:a5d1738d6abbdff3e81c10b7f86923ebcb340ca536e21e8c5ee7d938d263dba1

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add autoconf user, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash && \
  addgroup -g 101 autoconf && \
  adduser -h /var/cache/autoconf -g autoconf -s /bin/sh -G autoconf -D -H -u 101 autoconf && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/www && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  touch /etc/bunkerweb/autoconf.conf /etc/bunkerweb/config.yml && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:autoconf /data && \
  chmod -R 770 /data && \
  chown -R root:autoconf /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  chmod -R 770 /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  chmod 750 /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/autoconf/*.py /usr/share/bunkerweb/autoconf/entrypoint.sh /usr/share/bunkerweb/deps/python/bin/*

# Fix CVEs
RUN apk add --no-cache "libcrypto3>=3.1.4-r0" "libssl3>=3.1.4-r0"

WORKDIR /usr/share/bunkerweb/autoconf

USER autoconf:autoconf

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
