FROM python:3.11.3-alpine AS builder

# Copy python requirements
COPY src/scheduler/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
  cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 /tmp/req/requirements.txt.2 > /usr/share/bunkerweb/deps/requirements.txt && \
  rm -rf /tmp/req

# Install python dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --upgrade wheel && \
  mkdir -p /usr/share/bunkerweb/deps/python && \
  pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt

# Remove build dependencies
RUN apk del .build-deps

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/cli /usr/share/bunkerweb/cli
COPY src/common/confs /usr/share/bunkerweb/confs
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/scheduler /usr/share/bunkerweb/scheduler
COPY src/VERSION /usr/share/bunkerweb/VERSION

FROM python:3.11.3-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Add scheduler user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash libgcc libstdc++ openssl && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 scheduler && \
  adduser -h /var/cache/nginx -g scheduler -s /bin/sh -G scheduler -D -H -u 101 scheduler && \
  cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/www && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:scheduler /data && \
  chmod -R 770 /data && \
  chown -R root:scheduler /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb && \
  find /usr/share/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
  chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/gen/*.py /usr/share/bunkerweb/scheduler/main.py /usr/share/bunkerweb/scheduler/entrypoint.sh /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/deps/python/bin/* /usr/bin/bwcli && \
  mkdir -p /etc/nginx && \
  chown -R scheduler:scheduler /etc/nginx && \
  chmod -R 770 /etc/nginx && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:scheduler /usr/share/bunkerweb/INTEGRATION

COPY --chown=root:scheduler src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:scheduler src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb

RUN chmod 770 /var/tmp/bunkerweb/asn.mmdb /var/tmp/bunkerweb/country.mmdb

# Fix CVEs
# There are no CVEs for python:3.11.3-alpine at the moment

VOLUME /data /etc/nginx

WORKDIR /usr/share/bunkerweb/scheduler

USER scheduler:scheduler

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-scheduler.sh

ENTRYPOINT ["/usr/share/bunkerweb/scheduler/entrypoint.sh"]
