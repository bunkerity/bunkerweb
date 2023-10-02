FROM python:3.11.5-alpine@sha256:cd311c6a0164f34a7edbf364e05258b07d66d3f7bc155139dcb9bef88a186ded AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc build-base linux-headers

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/core/requirements.txt /tmp/req/requirements.txt
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.3

WORKDIR /usr/share/bunkerweb

RUN mkdir -p deps/python && \
  cat /tmp/req/requirements.txt* > deps/requirements.txt && \
  rm -rf /tmp/req

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --ignore-installed --require-hashes -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Clean up temporary dependencies
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/core core_plugins
COPY src/common/db db
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/VERSION VERSION

COPY src/core core

FROM python:3.11.5-alpine@sha256:cd311c6a0164f34a7edbf364e05258b07d66d3f7bc155139dcb9bef88a186ded

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add core user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash grep libmagic && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 core && \
  adduser -h /usr/share/bunkerweb/core -g core -s /bin/bash -G core -D -H -u 101 core && \
  cp helpers/bwcli /usr/bin/ && \
  echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /etc/nginx && \
  mkdir -p /run/secrets && \
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
  find core_plugins/*/jobs/* -type f -exec chmod 750 {} \; && \
  chmod 750 cli/main.py core/app/*.py core/app/routers/*.py core/entrypoint.sh helpers/*.sh deps/python/bin/* /usr/bin/bwcli && \
  chmod 660 INTEGRATION && \
  chown root:core INTEGRATION

COPY --chown=root:core src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:core src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb

RUN chmod 770 /var/tmp/bunkerweb/asn.mmdb /var/tmp/bunkerweb/country.mmdb

# Fix CVEs
# There are no CVE to fix for the moment

VOLUME /data

WORKDIR /usr/share/bunkerweb/core

EXPOSE 1337

USER core:core

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-core.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
