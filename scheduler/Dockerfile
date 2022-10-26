FROM python:3.11-rc-alpine

# Copy python requirements
COPY bw/deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build py3-pip g++ gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
  pip install wheel && \
  mkdir /opt/bunkerweb/deps/python && \
  pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
  apk del build

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY scheduler /opt/bunkerweb/scheduler
COPY bw/api /opt/bunkerweb/api
COPY bw/confs /opt/bunkerweb/confs
COPY bw/core /opt/bunkerweb/core
COPY bw/gen /opt/bunkerweb/gen
COPY bw/helpers /opt/bunkerweb/helpers
COPY bw/settings.json /opt/bunkerweb/settings.json
COPY db /opt/bunkerweb/db
COPY utils /opt/bunkerweb/utils
COPY VERSION /opt/bunkerweb/VERSION

# Add scheduler user, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash libgcc libstdc++ openssl git && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 scheduler && \
  adduser -h /var/cache/nginx -g scheduler -s /bin/sh -G scheduler -D -H -u 101 scheduler && \
  echo "Docker" > /opt/bunkerweb/INTEGRATION && \
  for dir in $(echo "cache configs configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs cache/letsencrypt plugins www") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
  chown -R scheduler:scheduler /data && \
  chmod -R 770 /data && \
  mkdir /opt/bunkerweb/tmp && \
  chown -R scheduler:scheduler /opt/bunkerweb && \
  find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
  find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
  chmod 770 /opt/bunkerweb/tmp && \
  chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/scheduler/main.py /opt/bunkerweb/scheduler/entrypoint.sh /opt/bunkerweb/helpers/*.sh /opt/bunkerweb/deps/python/bin/* && \
  find /opt/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
  mkdir /etc/nginx && \
  chown -R scheduler:scheduler /etc/nginx && \
  chmod -R 770 /etc/nginx && \
  chmod 660 /opt/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "libssl1.1>=1.1.1q-r0" "libcrypto1.1>=1.1.1q-r0" "git>=2.32.3-r0" "ncurses-libs>=6.2_p20210612-r1" "ncurses-terminfo-base>=6.2_p20210612-r1" "libtirpc>=1.3.2-r1" "libtirpc-conf>=1.3.2-r1" "zlib>=1.2.12-r2" "libxml2>=2.9.14-r1"

VOLUME /data /etc/nginx

WORKDIR /opt/bunkerweb/scheduler

USER root:scheduler

ENTRYPOINT ["/opt/bunkerweb/scheduler/entrypoint.sh"]
