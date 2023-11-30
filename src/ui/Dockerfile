FROM python:3.12.0-alpine3.18@sha256:f1d0d03700fb2d4480e89fb807e7346c14b88952f7bd58d56de54a24817cc2e8 AS builder

# Install python dependencies
# RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev file make

WORKDIR /tmp

# Copy python requirements
COPY src/deps/requirements.txt requirements-deps.txt
COPY src/ui/requirements.txt req/requirements-ui.txt
COPY src/common/db/requirements.txt req/requirements-db.txt
COPY src/common/gen/requirements.txt req/requirements-gen.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  mkdir -p deps/python && \
  pip install --no-cache-dir --require-hashes --ignore-installed -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Remove build dependencies
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

COPY src/ui ui

FROM python:3.12.0-alpine3.18@sha256:f1d0d03700fb2d4480e89fb807e7346c14b88952f7bd58d56de54a24817cc2e8

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
RUN apk add --no-cache "libcrypto3>=3.1.4-r1" "libssl3>=3.1.4-r1"

# Change working directory
WORKDIR /usr/share/bunkerweb/ui

# Initialize project
RUN cd client && \
  npm install

RUN node build.js

# Remove no longer needed files
RUN rm -rf client build.js

USER ui:ui

EXPOSE 7000

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
