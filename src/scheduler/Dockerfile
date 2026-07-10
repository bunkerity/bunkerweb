FROM python:3.14-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo patch

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/scheduler/requirements.txt /tmp/req/requirements-scheduler.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] || [ "$TARGETPLATFORM" = "linux/386" ] ; then mv /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.arm.txt ; fi && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Apply BunkerWeb patches to vendored Python deps (DNS alias / CNAME delegation for certbot).
# -F0 + --dry-run first so any context drift from a future certbot bump fails the build loudly
# instead of fuzzing onto the wrong code; the post-patch grep is a positive assertion that the
# expected marker landed in the patched file.
COPY src/deps/misc/certbot-dns-alias.patch /tmp/certbot-dns-alias.patch
RUN patch -p1 -F0 --dry-run -d /usr/share/bunkerweb/deps/python < /tmp/certbot-dns-alias.patch && \
  patch -p1 -F0 --no-backup-if-mismatch -d /usr/share/bunkerweb/deps/python < /tmp/certbot-dns-alias.patch && \
  grep -q '_load_domain_aliases' /usr/share/bunkerweb/deps/python/certbot/plugins/dns_common.py && \
  rm -f /tmp/certbot-dns-alias.patch

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

FROM python:3.14-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies and add scheduler user
RUN apk add --no-cache bash unzip curl libgcc libstdc++ libpq openssl libmagic mariadb-connector-c mariadb-client postgresql-client sqlite tzdata sed grep && \
  addgroup -g 101 scheduler && \
  adduser -h /usr/share/bunkerweb/scheduler -g scheduler -s /sbin/nologin -G scheduler -D -H -u 101 --disabled-password scheduler

# Fix CVEs
RUN apk add --no-cache "curl>=8.21.0-r0" # CVE-2026-11856 CVE-2026-8925 CVE-2026-8927 CVE-2026-9079 CVE-2026-10536 CVE-2026-11352 CVE-2026-11564 CVE-2026-11586 CVE-2026-12064 CVE-2026-8286 CVE-2026-8458 CVE-2026-8924 CVE-2026-8926 CVE-2026-9080 CVE-2026-9545 CVE-2026-9547 CVE-2026-8932 CVE-2026-9546
RUN apk add --no-cache "c-ares>=1.34.8-r0" # CVE-2026-33630

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
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
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
LABEL version="1.6.12"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="scheduler"

VOLUME /data

WORKDIR /usr/share/bunkerweb/scheduler

USER scheduler:scheduler

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-scheduler.sh

ENV PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db

ENTRYPOINT [ "./entrypoint.sh" ]
