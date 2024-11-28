FROM python:3.13-alpine@sha256:fcbcbbecdeae71d3b77445d9144d1914df55110f825ab62b04a66c7c33c09373 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/ui/requirements.txt /tmp/req/requirements-ui.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.armv7.txt /tmp/req/requirements-db.armv7.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] ; then mv /tmp/req/requirements-db.armv7.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.armv7.txt ; fi && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

WORKDIR /usr/share/bunkerweb

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/db db
COPY src/common/core core
COPY src/common/gen gen
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/common/helpers helpers
COPY src/VERSION VERSION
COPY src/ui ui

FROM python:3.13-alpine@sha256:fcbcbbecdeae71d3b77445d9144d1914df55110f825ab62b04a66c7c33c09373

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

COPY src/deps/requirements.txt /tmp/requirements-deps.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt

# Install runtime dependencies and add ui user
RUN apk add --no-cache bash unzip libmagic mariadb-connector-c mariadb-client postgresql-client sqlite tzdata && \
  addgroup -g 101 ui && \
  adduser -h /var/cache/nginx -g ui -s /bin/bash -G ui -D -H -u 101 ui

# Fix CVEs
RUN apk add --no-cache "libcrypto3>=3.3.2-r1" "libssl3>=3.3.2-r1" # CVE-2024-9143
RUN apk add --no-cache "libpq>=16.5-r0" "postgresql16-client>=16.5-r0" # CVE-2024-10976 CVE-2024-10977 CVE-2024-10978 CVE-2024-10979

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Create data folders and set permissions
RUN echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:ui INTEGRATION /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod -R 770 /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 750 gen/*.py ui/*.sh helpers/*.sh deps/python/bin/* && \
  find ui/ -type f -name "*.py" -print0 | xargs -0 chmod 750 && \
  chmod 660 INTEGRATION && \
  ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.0-beta"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="ui"

VOLUME /data

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

ENTRYPOINT [ "./entrypoint.sh" ]
