FROM python:3.12.5-alpine@sha256:c2f41e6a5a67bc39b95be3988dd19fbd05d1b82375c46d9826c592cca014d4de AS builder

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

# Install node and npm to build vite frontend
RUN apk add --no-cache nodejs npm

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

COPY src/ui/builder ui/builder
COPY src/ui/client ui/client

# This will build the frontend and add files to the UI folder
WORKDIR /usr/share/bunkerweb/ui/client
RUN DOCKERFILE=yes python3 build.py

# We can delete the client folder after building the frontend
RUN rm -rf /usr/share/bunkerweb/ui/client

WORKDIR /usr/share/bunkerweb

COPY src/ui/src ui/src
COPY src/ui/*.py ui/
COPY --chmod=750 src/ui/entrypoint.sh ui/

FROM python:3.12.5-alpine@sha256:c2f41e6a5a67bc39b95be3988dd19fbd05d1b82375c46d9826c592cca014d4de

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies and add ui user
RUN apk add --no-cache bash unzip libmagic mariadb-connector-c mariadb-client postgresql-client sqlite && \
  addgroup -g 101 ui && \
  adduser -h /var/cache/nginx -g ui -s /bin/bash -G ui -D -H -u 101 ui

# Fix CVEs
RUN apk add --no-cache "busybox>=1.36.1-r17" "busybox-binsh>=1.36.1-r17" "ssl_client>=1.36.1-r17" # CVE-2023-42363 CVE-2023-42364 CVE-2023-42365 CVE-2023-42366
RUN apk add --no-cache "libcrypto3>=3.1.6-r0" "libssl3>=3.1.6-r0" # CVE-2024-4741 CVE-2024-5535

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
  chmod 750 gen/*.py ui/*.py ui/src/*.py helpers/*.sh deps/python/bin/* && \
  chmod 660 INTEGRATION && \
  ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.5.9"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="ui"

VOLUME /data

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

ENTRYPOINT [ "./entrypoint.sh" ]
