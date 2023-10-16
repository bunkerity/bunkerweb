FROM nginx:1.24.0-alpine@sha256:76ca7f6bfe01c3e22e3af85fd37c30149ece3ac2a444973687cab1765abca115 AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache --virtual .build-deps bash autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev yajl yajl-dev yajl-tools py3-pip

WORKDIR /tmp/bunkerweb/deps

# Copy dependencies sources folder
COPY src/deps/misc misc
COPY src/deps/src src
COPY src/deps/deps.json deps.json
COPY src/deps/install.sh install.sh

# Compile and install dependencies
RUN mkdir -p /usr/share/bunkerweb/deps/python && \
	chmod +x install.sh && \
	bash install.sh

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/common/gen/requirements.txt deps/requirements.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
	pip install --no-cache-dir --ignore-installed --require-hashes -r /tmp/requirements-deps.txt && \
	pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Clean up temporary dependencies
RUN apk del .build-deps && \
	rm -rf /var/cache/apk/*

# Copy files
# can't exclude deps from . so we are copying everything by hand
COPY src/bw/entrypoint.sh entrypoint.sh
COPY src/bw/loading loading
COPY src/bw/lua lua
COPY src/bw/misc misc
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/core core_plugins
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/VERSION VERSION
COPY misc/*.ascii misc/

FROM nginx:1.24.0-alpine@sha256:76ca7f6bfe01c3e22e3af85fd37c30149ece3ac2a444973687cab1765abca115

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Install runtime dependencies, pypi packages, move bwcli, create data folders and set permissions
RUN apk add --no-cache pcre bash python3 yajl && \
	cp helpers/bwcli /usr/bin/ && \
	mkdir -p /var/tmp/bunkerweb && \
	mkdir -p /var/run/bunkerweb && \
	mkdir -p /var/log/bunkerweb && \
	mkdir -p /var/www/html && \
	mkdir -p /etc/bunkerweb && \
	mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
	for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
	for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
	chown -R root:nginx /data /etc/nginx /var/cache/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
	chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/tmp/bunkerweb /var/log/bunkerweb /var/run/bunkerweb && \
	chmod 750 cli/main.py gen/main.py helpers/*.sh entrypoint.sh /usr/bin/bwcli deps/python/bin/* && \
	rm -f /var/log/bunkerweb/* && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/error.log && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/modsec_audit.log && \
	ln -s /proc/1/fd/1 /var/log/bunkerweb/access.log

# Fix CVEs
RUN apk add --no-cache "libwebp>=1.2.4-r3" "curl>=8.3.0-r0" "libcurl>=8.3.0-r0" "nghttp2-libs>=1.51.0-r2"

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT [ "./entrypoint.sh" ]
