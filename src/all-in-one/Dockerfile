FROM nginx:1.26.3-alpine-slim@sha256:b72dec66dea425356956e863bfbccca6c1f8748f5913e094d4ca20b71e4ba2c3 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install temporary requirements for the dependencies
RUN apk add --no-cache bash autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev yajl yajl-dev yajl-tools py3-pip python3-dev libffi-dev postgresql-dev cargo

WORKDIR /tmp/bunkerweb/deps

# Copy dependencies sources folder
COPY src/deps/misc misc
COPY src/deps/src src
COPY src/deps/deps.json deps.json
COPY --chmod=644 src/deps/install.sh install.sh

# Compile and install dependencies
RUN bash install.sh

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/autoconf/requirements.txt /tmp/req/requirements-autoconf.txt
COPY src/scheduler/requirements.txt /tmp/req/requirements-scheduler.txt
COPY src/ui/requirements.txt /tmp/req/requirements-ui.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.armv7.txt /tmp/req/requirements-db.armv7.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
    if [ "$TARGETPLATFORM" = "linux/arm/v7" ] ; then mv /tmp/req/requirements-db.armv7.txt /tmp/req/requirements-db.txt ; else rm -f /tmp/req/requirements-db.armv7.txt ; fi && \
    pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
    pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Copy files
COPY src/bw/entrypoint.sh entrypoint.sh
COPY src/bw/loading loading
COPY src/bw/lua lua
COPY src/bw/misc misc
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/db db
COPY src/common/core core
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/autoconf autoconf
COPY src/scheduler scheduler
COPY src/ui ui
COPY src/VERSION VERSION
COPY misc/*.ascii misc/

FROM nginx:1.26.3-alpine-slim@sha256:b72dec66dea425356956e863bfbccca6c1f8748f5913e094d4ca20b71e4ba2c3

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies including supervisord
RUN apk add --no-cache bash curl geoip grep libgcc libgd libmagic libpq libstdc++ libxml2 mariadb-client mariadb-connector-c openssl pcre postgresql-client python3 sed sqlite tzdata unzip yajl supervisor

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Move bwcli, create data folders and set permissions
RUN cp helpers/bwcli /usr/bin/ && \
    echo "Docker" > INTEGRATION && \
	mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
	mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
	mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
	mkdir -p /data/www && ln -s /data/www /var/www/html && \
	for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
	for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
	chown -R root:nginx INTEGRATION /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
	chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/log/bunkerweb /var/run/bunkerweb && \
    find core/ -type f -name "*.sh" ! -path "core/modsecurity/files/*" -print0 | xargs -0 chmod 750 && \
    find core/ -type f -name "*.py" ! -path "core/modsecurity/files/*" -print0 | xargs -0 chmod 750 && \
    find ui/ -type f -name "*.py" -print0 | xargs -0 chmod 750 && \
	chmod 750 cli/main.py gen/*.py helpers/*.sh autoconf/main.py scheduler/main.py scheduler/entrypoint.sh ui/*.sh entrypoint.sh /usr/bin/bwcli deps/python/bin/* && \
    chmod 770 db/alembic db/alembic/alembic.ini db/alembic/env.py && \
    chmod 660 INTEGRATION && \
    mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chmod -R 755 /var/log/nginx && \
    rm -rf /var/log/bunkerweb/* && \
	ln -s /proc/1/fd/1 /var/log/bunkerweb/access.log && \
    ln -s /proc/1/fd/1 /var/log/bunkerweb/bunkerweb.stdout.log && \
    ln -s /proc/1/fd/1 /var/log/bunkerweb/autoconf.stdout.log && \
    ln -s /proc/1/fd/1 /var/log/bunkerweb/scheduler.stdout.log && \
    ln -s /proc/1/fd/1 /var/log/bunkerweb/ui.stdout.log && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/error.log && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/modsec_audit.log && \
    ln -s /proc/1/fd/2 /var/log/bunkerweb/bunkerweb.stderr.log && \
    ln -s /proc/1/fd/2 /var/log/bunkerweb/autoconf.stderr.log && \
    ln -s /proc/1/fd/2 /var/log/bunkerweb/scheduler.stderr.log && \
    ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.stderr.log

COPY --chown=root:nginx --chmod=770 src/bw/misc/asn.mmdb /var/tmp/bunkerweb/asn.mmdb
COPY --chown=root:nginx --chmod=770 src/bw/misc/country.mmdb /var/tmp/bunkerweb/country.mmdb

# Set up supervisor configuration
RUN mkdir -p /etc/supervisor.d
COPY src/all-in-one/supervisord.conf /etc/supervisord.conf
COPY src/all-in-one/supervisor.d/*.ini /etc/supervisor.d/

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.1"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="all-in-one"
LABEL bunkerweb.INSTANCE="bunkerweb"

VOLUME /data

EXPOSE 8080/tcp 8443/tcp 8443/udp 7000/tcp

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-all-in-one.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db"
ENV SERVICE_UI="yes"
ENV SERVICE_SCHEDULER="yes"

USER nginx:nginx

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
