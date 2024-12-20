FROM python:3.13-alpine@sha256:fcbcbbecdeae71d3b77445d9144d1914df55110f825ab62b04a66c7c33c09373 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/autoconf/requirements.txt /tmp/req/requirements-autoconf.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.armv7.txt /tmp/req/requirements-db.armv7.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] ; then mv /tmp/req/requirements-db.armv7.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.armv7.txt ; fi && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/core core
COPY src/common/db db
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/autoconf autoconf
COPY src/VERSION VERSION

FROM python:3.13-alpine@sha256:fcbcbbecdeae71d3b77445d9144d1914df55110f825ab62b04a66c7c33c09373

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install bash and create autoconf user
RUN apk add --no-cache bash tzdata && \
  addgroup -g 101 autoconf && \
  adduser -h /var/cache/autoconf -g autoconf -s /bin/sh -G autoconf -D -H -u 101 autoconf

# Fix CVEs
RUN apk add --no-cache "libcrypto3>=3.3.2-r1" "libssl3>=3.3.2-r1" # CVE-2024-9143

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Drop bwcli, install runtime dependencies, create data folders and set permissions
RUN cp helpers/bwcli /usr/bin/ && \
  echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:autoconf INTEGRATION /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  find core/ -type f -name "*.sh" ! -path "core/modsecurity/files/*" -print0 | xargs -0 chmod 750 && \
  find core/ -type f -name "*.py" ! -path "core/modsecurity/files/*" -print0 | xargs -0 chmod 750 && \
  chmod 750 cli/main.py autoconf/main.py helpers/*.sh deps/python/bin/* /usr/bin/bwcli && \
  chmod 660 INTEGRATION

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.0-rc1"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="autoconf"

VOLUME /data

WORKDIR /usr/share/bunkerweb/autoconf

USER autoconf:autoconf

HEALTHCHECK --interval=10s --timeout=10s --start-period=60s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

CMD [ "python3", "main.py" ]
