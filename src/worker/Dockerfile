FROM python:3.13-alpine@sha256:db66119d6609a3a941a9433b225f4e13d33c459cede097cf3ec2fc4d1bd314b2 AS builder

ARG TARGETPLATFORM

RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo

COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/scheduler/requirements.txt /tmp/req/requirements-scheduler.txt
COPY src/worker/requirements.txt /tmp/req/requirements-worker.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt

WORKDIR /usr/share/bunkerweb

RUN export MAKEFLAGS="-j$(nproc)" && \
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

FROM python:3.13-alpine@sha256:db66119d6609a3a941a9433b225f4e13d33c459cede097cf3ec2fc4d1bd314b2

RUN umask 027

RUN apk add --no-cache bash curl libgcc libstdc++ libpq openssl libmagic mariadb-connector-c tzdata && \
  addgroup -g 102 worker && \
  adduser -h /usr/share/bunkerweb/worker -g worker -s /sbin/nologin -G worker -D -H -u 102 --disabled-password worker

RUN apk add --no-cache "zlib>=1.3.2-r0"

COPY --from=builder --chown=0:102 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

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
LABEL version="1.6.10~rc1"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="worker"

VOLUME /data

WORKDIR /usr/share/bunkerweb/worker

USER worker:worker

HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 CMD /usr/share/bunkerweb/helpers/healthcheck-worker.sh

ENV PYTHONPATH=/usr/share/bunkerweb:/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db:/usr/share/bunkerweb/utils:/usr/share/bunkerweb/api
ENV PATH=/usr/share/bunkerweb/deps/python/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

ENTRYPOINT [ "./entrypoint.sh" ]
