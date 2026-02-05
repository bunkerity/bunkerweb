FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/scheduler/requirements.txt /tmp/req/requirements-scheduler.txt
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

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/core core
COPY src/common/db db
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/scheduler scheduler
COPY src/VERSION VERSION

FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies and add scheduler user
RUN apk add --no-cache bash unzip libgcc libstdc++ libpq openssl libmagic mariadb-connector-c mariadb-client postgresql-client sqlite tzdata sed grep && \
  addgroup -g 101 scheduler && \
  adduser -h /usr/share/bunkerweb/scheduler -g scheduler -s /sbin/nologin -G scheduler -D -H -u 101 --disabled-password scheduler

# Fix CVEs
# There are no CVEs for the following packages

# Copy dependencies
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Drop bwcli, install runtime dependencies, create data folders and set permissions
RUN cp helpers/bwcli /usr/bin/ && \
  echo "Docker" > INTEGRATION && \
  mkdir -p /etc/nginx /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:scheduler INTEGRATION /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod 2770 /var/tmp/bunkerweb && \
  find . \( -path './scheduler' -o -path './cli' -o -path './core' -o -path './db' -o -path './gen' -o -path './utils' -o -path './helpers' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find scheduler cli core db gen utils helpers deps -type f ! -path 'deps/python/bin/*' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 770 -R db/alembic && \
  chmod 660 INTEGRATION


COPY --chown=root:scheduler --chmod=770 src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:scheduler --chmod=770 src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.8~rc3"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="scheduler"

VOLUME /data

WORKDIR /usr/share/bunkerweb/scheduler

USER scheduler:scheduler

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-scheduler.sh

ENV PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db

ENTRYPOINT [ "./entrypoint.sh" ]
