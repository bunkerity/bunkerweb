FROM python:3.12.1-alpine3.18@sha256:af0d8da43677e3000ebdf4045508d891a87e7bd2d3ec87bc6e40403be97291b8 AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache g++ gcc build-base linux-headers

WORKDIR /tmp

# Copy python requirements
COPY src/deps/requirements.txt requirements-deps.txt
COPY src/ui/requirements.txt req/requirements-ui.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  mkdir -p deps/python && \
  pip install --no-cache-dir --require-hashes --ignore-installed -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python -r /tmp/req/requirements-ui.txt

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

COPY src/ui ui

FROM python:3.12.1-alpine3.18@sha256:af0d8da43677e3000ebdf4045508d891a87e7bd2d3ec87bc6e40403be97291b8

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add ui user, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash nodejs npm && \
  addgroup -g 101 ui && \
  adduser -h /usr/share/bunkerweb/ui -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /var/log/bunkerweb/ && \
  touch /etc/bunkerweb/ui.conf /etc/bunkerweb/config.yml && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:ui /data && \
  chmod -R 770 /data && \
  chown -R root:ui /usr/share/bunkerweb/INTEGRATION /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 770 /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 750 /usr/share/bunkerweb/ui/*.js /usr/share/bunkerweb/ui/*.sh /usr/share/bunkerweb/ui/*.py /usr/share/bunkerweb/ui/routes/*.py /usr/share/bunkerweb/deps/python/bin/* /usr/share/bunkerweb/helpers/*.sh && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:ui /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /usr/share/bunkerweb/ui/.npm /usr/share/bunkerweb/ui/static && \
  chown -R ui:ui /usr/share/bunkerweb/ui/.npm /usr/share/bunkerweb/ui/static && \
  ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

# Fix CVEs
RUN apk add --no-cache "libcrypto3>=3.1.4-r3" "libssl3>=3.1.4-r3"

# Change working directory
WORKDIR /usr/share/bunkerweb/ui

# Init needed dashboard package to build
RUN cd client && \
  npm install

# Init setup standalone page
RUN cd setup && \
  npm install

# Build ui
RUN node build.js

# Remove no longer needed files
RUN rm -rf client setup build.js

USER ui:ui

EXPOSE 7000

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
