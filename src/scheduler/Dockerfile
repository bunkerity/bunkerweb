FROM python:3.11.4-alpine AS builder

# Install python dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev

# Copy python requirements
COPY src/scheduler/requirements.txt /usr/share/bunkerweb/deps/requirements.txt

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
COPY src/common/cli /usr/share/bunkerweb/cli
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/VERSION /usr/share/bunkerweb/VERSION

COPY src/scheduler /usr/share/bunkerweb/scheduler

FROM python:3.11.4-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Add scheduler user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash libgcc libstdc++ openssl libmagic && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 scheduler && \
  adduser -h /var/cache/nginx -g scheduler -s /bin/sh -G scheduler -D -H -u 101 scheduler && \
  cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  touch /etc/bunkerweb/scheduler.conf /etc/bunkerweb/config.yaml && \
  chown -R root:scheduler /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  find /usr/share/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
  chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/scheduler/*.py /usr/share/bunkerweb/scheduler/entrypoint.sh /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/deps/python/bin/* /usr/bin/bwcli && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:scheduler /usr/share/bunkerweb/INTEGRATION

COPY --chown=root:scheduler src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:scheduler src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb

RUN chmod 770 /var/tmp/bunkerweb/asn.mmdb /var/tmp/bunkerweb/country.mmdb

# Fix CVEs
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

VOLUME /data /etc/nginx

WORKDIR /usr/share/bunkerweb/scheduler

USER scheduler:scheduler

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-scheduler.sh

ENTRYPOINT ["/usr/share/bunkerweb/scheduler/entrypoint.sh"]
