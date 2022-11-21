FROM python:3.10-alpine

# Copy python requirements
COPY src/scheduler/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
  cat /tmp/req/requirements.txt /tmp/req/requirements.txt.1 /tmp/req/requirements.txt.2 > /usr/share/bunkerweb/deps/requirements.txt && \
  rm -rf /tmp/req

# Install python requirements
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev && \
  pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --upgrade setuptools wheel && \
  mkdir -p /usr/share/bunkerweb/deps/python && \
  pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt && \
  pip install --no-cache-dir gunicorn && \
  apk del .build-deps

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/confs /usr/share/bunkerweb/confs
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/scheduler /usr/share/bunkerweb/scheduler
COPY src/VERSION /usr/share/bunkerweb/VERSION

# Add scheduler user, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash libgcc libstdc++ openssl && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 scheduler && \
  adduser -h /var/cache/nginx -g scheduler -s /bin/sh -G scheduler -D -H -u 101 scheduler && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/www && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/cache/letsencrypt && ln -s /data/cache/letsencrypt /etc/letsencrypt && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:scheduler /data && \
  chmod -R 770 /data && \
  chown -R root:scheduler /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb && \
  for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type f -exec chmod 0740 {} \; ; done && \
  for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type d -exec chmod 0750 {} \; ; done && \
  chmod -R 770 /var/cache/bunkerweb /var/lib/bunkerweb /var/tmp/bunkerweb && \
  find /usr/share/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
  chmod 750 /usr/share/bunkerweb/gen/*.py /usr/share/bunkerweb/scheduler/main.py /usr/share/bunkerweb/scheduler/entrypoint.sh /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/deps/python/bin/* && \
  mkdir /etc/nginx && \
  chown -R scheduler:scheduler /etc/nginx && \
  chmod -R 770 /etc/nginx && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1" "expat>=2.5.0-r0"

VOLUME /data /etc/nginx

WORKDIR /usr/share/bunkerweb/scheduler

USER root:scheduler

ENTRYPOINT ["/usr/share/bunkerweb/scheduler/entrypoint.sh"]
