FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83 AS builder

ARG TARGETPLATFORM

# Build-time deps
RUN apt-get update && \
  apt-get install -y --no-install-recommends build-essential libffi-dev libpq-dev cargo zlib1g-dev && \
  rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/api/requirements.txt /tmp/req/requirements-api.txt
COPY src/worker/requirements.txt /tmp/req/requirements-worker.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
# The API only needs celery/redis from the worker requirements (it dispatches jobs via
# celery.send_task). Strip the certbot stack — the API never runs certbot, so there is no need to
# pull in the certbot-dns-multi Go/CGO bridge. (Same awk strip pattern the worker Dockerfile uses
# for schedule==.)
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] || [ "$TARGETPLATFORM" = "linux/386" ] ; then mv /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.arm.txt ; fi && \
  awk 'BEGIN {skip=0} skip { if ($0 ~ /^    --hash=/ || $0 ~ /^    #/ || $0 == "") next; skip=0 } /^(acme|certbot|certbot-dns-multi)==/ { skip=1; next } { print }' /tmp/req/requirements-worker.txt > /tmp/req/requirements-worker.txt.new && \
  mv /tmp/req/requirements-worker.txt.new /tmp/req/requirements-worker.txt && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Copy shared code and service
COPY src/common/api api
COPY src/common/db db
COPY src/common/utils utils
COPY src/common/helpers helpers
# Core plugins: needed on disk so the API can discover and mount plugin-shipped
# API/DB extensions (api/router.py, db/models.py) — only plugins declaring an
# "extensions" block are imported; the rest are inert files.
COPY src/common/core core
COPY src/VERSION VERSION
COPY src/api api

FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83

RUN umask 027

COPY src/deps/requirements.txt /tmp/requirements-deps.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages --ignore-installed -r /tmp/requirements-deps.txt

# Install runtime dependencies and add api user
# PostgreSQL client 18 (PGDG). Debian trixie only ships 17 and pg_dump refuses any server newer
# than itself, so the bundled client must be >= the newest PostgreSQL the product supports.
# The signing key is checked in (fingerprint B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8,
# "PostgreSQL Debian Repository") so no key is fetched over the network at build time.
# PGDG publishes amd64 and arm64 only -- binary-i386 and binary-armhf 404 -- while the release
# workflow builds linux/386 and linux/arm/v7 as well, so those two keep the distribution's client
# and its 17-server ceiling. Adding the repository unconditionally fails their build outright.
COPY --chmod=644 src/deps/pgdg-archive-keyring.asc /etc/apt/keyrings/pgdg.asc

RUN . /etc/os-release && \
  case "$(dpkg --print-architecture)" in \
  amd64|arm64) echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list; PGCLIENT=postgresql-client-18 ;; \
  *) PGCLIENT=postgresql-client ;; \
  esac && \
  apt-get update && \
  apt-get install -y --no-install-recommends bash unzip ca-certificates libmariadb3 mariadb-client sqlite3 "$PGCLIENT" tzdata && \
  rm -rf /var/lib/apt/lists/* && \
  groupadd -g 101 api && \
  useradd -u 101 -g api -d /usr/share/bunkerweb/api -s /usr/sbin/nologin -M api

# Fix CVEs
RUN apt-get update && apt-get install -y --no-install-recommends bsdutils libblkid1 liblastlog2-2 libmount1 libsmartcols1 libuuid1 login mount openssl util-linux && rm -rf /var/lib/apt/lists/* # util-linux 2.41-5 -> 2.41.5-0+deb13u1 and openssl 3.5.6-1~deb13u2 -> 3.5.7-1~deb13u2 (openssl drags libssl3t64 + openssl-provider-legacy with it), both still shipped vulnerable by the base image: CVE-2025-14104 CVE-2026-13595 CVE-2026-27456 CVE-2026-53612 CVE-2026-53613 CVE-2026-53614 CVE-2026-53615 CVE-2026-14456 CVE-2026-14457 CVE-2026-18798 CVE-2026-54874 CVE-2026-63072 CVE-2026-63073 CVE-2026-63074 CVE-2026-63075 CVE-2026-63076 CVE-2026-75803

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
LABEL version="1.7.0~beta"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="api"

VOLUME /data

EXPOSE 8888

WORKDIR /usr/share/bunkerweb/api

USER api:api

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-api.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

ENTRYPOINT [ "./entrypoint.sh" ]
