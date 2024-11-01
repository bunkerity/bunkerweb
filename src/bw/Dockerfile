FROM nginx:1.26.2-alpine-slim@sha256:6a3378d408c49073bdbb0243219db1072f338b979b58660577a744044515f9f7 AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache bash autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev yajl yajl-dev yajl-tools py3-pip

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
COPY src/common/gen/requirements.txt deps/requirements-gen.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
	pip install --break-system-packages --no-cache-dir --require-hashes --ignore-installed -r /tmp/requirements-deps.txt && \
	pip install --break-system-packages --no-cache-dir --require-hashes --target deps/python -r deps/requirements-gen.txt

# Copy files
# can't exclude deps from . so we are copying everything by hand
COPY src/bw/entrypoint.sh entrypoint.sh
COPY src/bw/loading loading
COPY src/bw/lua lua
COPY src/bw/misc misc
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/core core
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/VERSION VERSION
COPY misc/*.ascii misc/

FROM nginx:1.26.2-alpine-slim@sha256:6a3378d408c49073bdbb0243219db1072f338b979b58660577a744044515f9f7

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Install runtime dependencies, pypi packages, move bwcli, create data folders and set permissions
RUN apk add --no-cache openssl pcre bash python3 yajl geoip libxml2 libgd curl && \
	cp helpers/bwcli /usr/bin/ && \
	mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www/html && \
	mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
	for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
	for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
	chown -R root:nginx /data /etc/nginx /var/cache/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
	chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/log/bunkerweb /var/run/bunkerweb && \
	chmod 750 cli/main.py gen/main.py helpers/*.sh entrypoint.sh /usr/bin/bwcli deps/python/bin/* && \
	rm -f /var/log/bunkerweb/* && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/error.log && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/modsec_audit.log && \
	ln -s /proc/1/fd/1 /var/log/bunkerweb/access.log

# Fix CVEs
RUN apk add --no-cache "curl>=8.9.1-r0" "libcurl>=8.9.1-r0" "pyc>=3.12.3-r2" "python3>=3.12.3-r2" "python3-pyc>=3.12.3-r2" "python3-pycache-pyc0>=3.12.3-r2" # CVE-2024-7264 CVE-2024-8088
RUN apk add --no-cache "libcrypto3>=3.3.2-r1" "libssl3>=3.3.2-r1" "openssl>=3.3.2-r1" # CVE-2024-6119

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.5.11"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="bunkerweb"
LABEL bunkerweb.INSTANCE="bunkerweb"

EXPOSE 8080/tcp 8443/tcp 8443/udp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT [ "./entrypoint.sh" ]
