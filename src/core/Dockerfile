FROM python:3.11.4-alpine AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc

# Copy python requirements
COPY src/core/requirements.txt /tmp/req/requirements.txt
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
  cat /tmp/req/requirements.txt* > /usr/share/bunkerweb/deps/requirements.txt && \
  rm -rf /tmp/req

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
  mkdir -p /usr/share/bunkerweb/deps/python && \
  pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt

# Clean up temporary dependencies
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/cli /usr/share/bunkerweb/cli
COPY src/common/confs /usr/share/bunkerweb/confs
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/VERSION /usr/share/bunkerweb/VERSION

COPY src/core /usr/share/bunkerweb/core

FROM python:3.11.4-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Add core user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash jq grep libmagic && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 core && \
  adduser -h /var/cache/nginx -g core -s /bin/bash -G core -D -H -u 101 core && \
  cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /etc/nginx && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /var/log/bunkerweb && \
  mkdir -p /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  touch /etc/bunkerweb/core.conf /etc/bunkerweb/config.yaml && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:core /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/core/*.py /usr/share/bunkerweb/core/entrypoint.sh /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/deps/python/bin/* /usr/bin/bwcli && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:core /usr/share/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

VOLUME /data

WORKDIR /usr/share/bunkerweb/core

EXPOSE 5000

USER core:core

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-core.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT ["/usr/share/bunkerweb/core/entrypoint.sh"]

