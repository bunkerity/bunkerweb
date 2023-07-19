FROM python:3.11.4-alpine AS builder

# Copy python requirements
COPY src/api/requirements.txt /tmp/req/requirements.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt.1
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.2

RUN mkdir -p /usr/share/bunkerweb/deps && \
  cat /tmp/req/requirements.txt* > /usr/share/bunkerweb/deps/requirements.txt && \
  rm -rf /tmp/req

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
  mkdir -p /usr/share/bunkerweb/deps/python && \
  pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt

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
COPY src/VERSION /usr/share/bunkerweb/VERSION

COPY src/api /usr/share/bunkerweb/api

FROM python:3.11.4-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Add api user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash grep libmagic && \
  ln -s /usr/local/bin/python3 /usr/bin/python3 && \
  addgroup -g 101 api && \
  adduser -h /var/cache/nginx -g api -s /bin/bash -G api -D -H -u 101 api && \
  cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mv /usr/share/bunkerweb/api/api.conf /etc/bunkerweb/api.conf && \
  for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  chown -R root:api /data /usr/bin/bwcli /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  chmod -R 770 /data /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/api/*.py /usr/share/bunkerweb/api/entrypoint.sh /usr/share/bunkerweb/deps/python/bin/* /usr/bin/bwcli && \
  chmod 660 /usr/share/bunkerweb/INTEGRATION && \
  chown root:api /usr/share/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

VOLUME /data

WORKDIR /usr/share/bunkerweb/api

EXPOSE 5000

USER api:api

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-api.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT ["/usr/share/bunkerweb/api/entrypoint.sh"]

