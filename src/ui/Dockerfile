FROM python:3.12.0-alpine@sha256:a4029bd4a6ccfc9d23099f7c7fd808b7fe82ed8a625814ac524fc00017c9af6c AS builder

# Install python dependencies
# RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev file make

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/ui/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

WORKDIR /usr/share/bunkerweb

RUN mkdir -p deps/python && \
  cat /tmp/req/requirements.txt* > deps/requirements.txt && \
  rm -rf /tmp/req

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/ui/requirements.txt deps/requirements.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --ignore-installed --require-hashes -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Remove build dependencies
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

COPY src/ui ui

FROM python:3.12.0-alpine@sha256:a4029bd4a6ccfc9d23099f7c7fd808b7fe82ed8a625814ac524fc00017c9af6c

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add ui user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash && \
  addgroup -g 101 ui && \
  adduser -h /var/cache/nginx -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /var/log/bunkerweb/ && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:ui /data && \
  chmod -R 770 /data && \
  chown -R root:ui /usr/share/bunkerweb/INTEGRATION /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 770 /var/cache/bunkerweb /var/lib/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 750 /usr/share/bunkerweb/gen/*.py /usr/share/bunkerweb/ui/*.py /usr/share/bunkerweb/ui/src/*.py /usr/share/bunkerweb/deps/python/bin/* /usr/share/bunkerweb/helpers/*.sh && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:ui /usr/share/bunkerweb/INTEGRATION && \
  ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

# Fix CVEs
# There are no CVE to fix for the moment

USER ui:ui

# Change working directory
WORKDIR /usr/share/bunkerweb/ui/nuxt

# Initialize project
RUN npm install

# Build project
RUN npm run build

# Remove no longer needed files
RUN rm -rf .nuxtignore assets components composables layouts node_modules nuxt.config.ts pages public server tsconfig.json utils

# Change working directory
WORKDIR /usr/share/bunkerweb/ui

EXPOSE 7000

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
