FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83 AS builder

ARG TARGETPLATFORM

# Build toolchain. On amd64/arm64 every dependency installs from a manylinux wheel (no
# compilation), but the toolchain is kept for the 32-bit certbot-dns-multi sdist build below.
RUN apt-get update && \
  apt-get install -y --no-install-recommends build-essential libffi-dev libpq-dev curl ca-certificates jq wget && \
  rm -rf /var/lib/apt/lists/*

COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/scheduler/requirements.txt /tmp/req/requirements-scheduler.txt
COPY src/worker/requirements.txt /tmp/req/requirements-worker.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt

# Pinned Go toolchain (reused from the all-in-one build) — only used to compile the
# certbot-dns-multi sdist on 32-bit arches, which have no prebuilt wheel.
COPY src/all-in-one/deps/go.json /tmp/go/go.json
COPY --chmod=644 src/all-in-one/scripts/install-go.sh /tmp/go/install-go.sh
COPY --chmod=644 src/all-in-one/scripts/utils.sh /tmp/go/utils.sh

WORKDIR /usr/share/bunkerweb

# certbot-dns-multi ships glibc manylinux wheels for x86_64 + aarch64 (loaded directly on this
# glibc image — the Go/CGO bridge cannot load on musl, which is why the worker is not Alpine).
# linux/arm/v7 and linux/386 have no wheel, so pip builds the Go/CGO sdist there, which needs
# Go 1.25 (newer than Debian's package) — fetched via the pinned upstream toolchain.
RUN export MAKEFLAGS="-j$(nproc)" && export CGO_ENABLED=1 && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] || [ "$TARGETPLATFORM" = "linux/386" ]; then \
  cd /tmp/go && \
  export PLATFORM="$(case "$TARGETPLATFORM" in linux/arm/v7) echo armv6l ;; linux/386) echo 386 ;; esac)" && \
  export VERSION="$(jq -r .version go.json)" && \
  export URL="$(jq -r .url go.json | sed "s/{VERSION}/$VERSION/" | sed "s/{PLATFORM}/$PLATFORM/")" && \
  export SHA256="$(if [ "$PLATFORM" = "386" ]; then jq -r '.checksums."386"' go.json; else jq -r ".checksums.$PLATFORM" go.json; fi)" && \
  bash install-go.sh && cd /usr/share/bunkerweb ; \
  fi && \
  export PATH="/usr/local/go/bin:$PATH" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] || [ "$TARGETPLATFORM" = "linux/386" ] ; then mv /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.arm.txt ; fi && \
  awk 'BEGIN {skip=0} skip { if ($0 ~ /^    --hash=/ || $0 ~ /^    #/ || $0 == "") next; skip=0 } /^schedule==/ { skip=1; next } { print }' /tmp/req/requirements-scheduler.txt > /tmp/req/requirements-scheduler.txt.new && \
  mv /tmp/req/requirements-scheduler.txt.new /tmp/req/requirements-scheduler.txt && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

COPY src/common/api api
COPY src/common/confs confs
COPY src/common/core core
COPY src/common/db db
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/worker worker
COPY src/VERSION VERSION

FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83

RUN umask 027

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
  apt-get install -y --no-install-recommends bash curl ca-certificates libpq5 openssl libmagic1 libmariadb3 sqlite3 mariadb-client "$PGCLIENT" tzdata && \
  rm -rf /var/lib/apt/lists/* && \
  groupadd -g 101 worker && \
  useradd -u 101 -g worker -d /usr/share/bunkerweb/worker -s /usr/sbin/nologin -M worker

# Fix CVEs
RUN apt-get update && apt-get install -y --no-install-recommends bsdutils libblkid1 liblastlog2-2 libmount1 libsmartcols1 libuuid1 login mount util-linux && rm -rf /var/lib/apt/lists/* # util-linux 2.41-5 -> 2.41.5-0+deb13u1, still shipped vulnerable by the base image: CVE-2025-14104 CVE-2026-13595 CVE-2026-27456 CVE-2026-53612 CVE-2026-53613 CVE-2026-53614 CVE-2026-53615

# 101:101, the same ids the scheduler, API and UI images use, so a stack backed by SQLite can
# hand all of them the one /data volume holding the database file. The all-in-one image already
# runs the worker under those ids (supervisor.d/worker.ini runs it as nginx), and the shared
# helpers/data.sh preflight names "uid 101 and gid 101" in every error it prints -- a worker on
# any other id was the odd one out, and it cost the SQLite quickstart every background job.
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

RUN echo "Docker" > INTEGRATION && \
  mkdir -p /etc/nginx /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:worker INTEGRATION /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 2770 /var/tmp/bunkerweb && \
  find . \( -path './worker' -o -path './api' -o -path './core' -o -path './db' -o -path './gen' -o -path './utils' -o -path './helpers' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find worker api core db gen utils helpers deps -type f ! -path 'deps/python/bin/*' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 770 -R db/alembic && \
  chmod 660 INTEGRATION

COPY --chown=root:worker --chmod=770 src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:worker --chmod=770 src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb
COPY --chown=root:worker --chmod=550 src/worker/healthcheck-worker.sh /usr/share/bunkerweb/helpers/healthcheck-worker.sh

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.7.0~beta"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="worker"

VOLUME /data

WORKDIR /usr/share/bunkerweb/worker

USER worker:worker

HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 CMD /usr/share/bunkerweb/helpers/healthcheck-worker.sh

ENV PYTHONPATH=/usr/share/bunkerweb:/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db:/usr/share/bunkerweb/utils:/usr/share/bunkerweb/api
ENV PATH=/usr/share/bunkerweb/deps/python/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

ENTRYPOINT [ "./entrypoint.sh" ]
