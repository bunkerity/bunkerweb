FROM nginx:1.24.0-alpine AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache --virtual .build-deps bash autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev yajl yajl-dev yajl-tools

# Copy dependencies sources folder
COPY src/deps /tmp/bunkerweb/deps

# Compile and install dependencies
RUN mkdir -p /usr/share/bunkerweb/deps && \
	chmod +x /tmp/bunkerweb/deps/install.sh && \
	bash /tmp/bunkerweb/deps/install.sh

# Clean up temporary dependencies
RUN apk del .build-deps && \
	rm -rf /var/cache/apk/*

# Copy python requirements
COPY src/common/gen/requirements.txt /usr/share/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual .build-deps py3-pip && \
	mkdir -p /usr/share/bunkerweb/deps/python && \
	export MAKEFLAGS="-j$(nproc)" && \
	pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
	pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt && \
	apk del .build-deps && \
	rm -rf /var/cache/apk/*

# Copy files
# can't exclude deps from . so we are copying everything by hand
COPY src/bw/entrypoint.sh /usr/share/bunkerweb/entrypoint.sh
COPY src/bw/loading /usr/share/bunkerweb/loading
COPY src/bw/lua /usr/share/bunkerweb/lua
COPY src/bw/misc /usr/share/bunkerweb/misc
COPY src/common/api /usr/share/bunkerweb/api
COPY src/common/cli /usr/share/bunkerweb/cli
COPY src/common/confs /usr/share/bunkerweb/confs
COPY src/common/core /usr/share/bunkerweb/core
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/VERSION /usr/share/bunkerweb/VERSION
COPY misc/*.ascii /usr/share/bunkerweb/misc/

FROM nginx:1.24.0-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

# Install runtime dependencies, pypi packages, move bwcli, create data folders and set permissions
RUN apk add --no-cache pcre bash python3 yajl && \
	cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
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
	chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/gen/main.py /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/entrypoint.sh /usr/bin/bwcli /usr/share/bunkerweb/deps/python/bin/* && \
	rm -f /var/log/bunkerweb/* && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/error.log && \
	ln -s /proc/1/fd/2 /var/log/bunkerweb/modsec_audit.log && \
	ln -s /proc/1/fd/1 /var/log/bunkerweb/access.log

# Fix CVEs
RUN apk add --no-cache "libwebp>=1.2.4-r3"

VOLUME /data /etc/nginx

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT ["/usr/share/bunkerweb/entrypoint.sh"]
