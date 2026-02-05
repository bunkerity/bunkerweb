FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4 AS builder

ARG TARGETPLATFORM

# Build-time deps
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo zlib-dev

# Copy requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/api/requirements.txt /tmp/req/requirements-api.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt
COPY src/common/db/requirements.386.txt /tmp/req/requirements-db.386.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] ; then mv /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.txt && rm -f /tmp/req/requirements-db.386.txt ; elif [ "$TARGETPLATFORM" = "linux/386" ] ; then mv /tmp/req/requirements-db.386.txt /tmp/req/requirements-db.txt && rm -f /tmp/req/requirements-db.arm.txt ; else rm -f /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.386.txt ; fi && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Copy shared code and service
COPY src/common/api api
COPY src/common/db db
COPY src/common/utils utils
COPY src/common/helpers helpers
COPY src/VERSION VERSION
COPY src/api api

FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4

RUN umask 027

COPY src/deps/requirements.txt /tmp/requirements-deps.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt

# Install runtime dependencies and add api user
RUN apk add --no-cache bash unzip mariadb-connector-c mariadb-client postgresql-client sqlite tzdata && \
  addgroup -g 101 api && \
  adduser -h /usr/share/bunkerweb/api -g api -s /sbin/nologin -G api -D -H -u 101 --disabled-password api

# Fix CVEs
# There are no CVEs for the following packages

# Copy deps and app
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Set up minimal data dirs and permissions
RUN echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  chown -R root:api INTEGRATION /data /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod -R 770 /data /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  find . \( -path './api' -o -path './db' -o -path './utils' -o -path './helpers' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find api db utils helpers deps -type f ! -path 'deps/python/bin/*' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 660 INTEGRATION

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.8~rc3"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="api"

VOLUME /data

EXPOSE 8888

WORKDIR /usr/share/bunkerweb/api

USER api:api

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-api.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

ENTRYPOINT [ "./entrypoint.sh" ]
