FROM nginx:1.22.1-alpine AS builder

# Copy dependencies sources folder
COPY src/deps /tmp/bunkerweb/deps

# Compile and install dependencies
RUN apk add --no-cache --virtual build bash build autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev && \
	mkdir -p /usr/share/bunkerweb/deps && \
	chmod +x /tmp/bunkerweb/deps/install.sh && \
	bash /tmp/bunkerweb/deps/install.sh && \
	apk del build

# Copy python requirements
COPY src/common/gen/requirements.txt /usr/share/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build py3-pip && \
	pip install --no-cache-dir --upgrade pip && \
	pip install wheel && \
	mkdir -p /usr/share/bunkerweb/deps/python && \
	pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt && \
	apk del build

FROM nginx:1.22.1-alpine

# Copy dependencies
COPY --from=builder /usr/share/bunkerweb /usr/share/bunkerweb

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
COPY src/common/db /usr/share/bunkerweb/db
COPY src/common/gen /usr/share/bunkerweb/gen
COPY src/common/helpers /usr/share/bunkerweb/helpers
COPY src/common/settings.json /usr/share/bunkerweb/settings.json
COPY src/common/utils /usr/share/bunkerweb/utils
COPY src/VERSION /usr/share/bunkerweb/VERSION

# Install runtime dependencies, pypi packages, move bwcli, create data folders and set permissions
RUN apk add --no-cache pcre bash python3 && \
	cp /usr/share/bunkerweb/helpers/bwcli /usr/bin/ && \
	echo "Docker" > /usr/share/bunkerweb/INTEGRATION && \
	mkdir -p /var/tmp/bunkerweb && \
	mkdir -p /var/www && \
	mkdir -p /etc/bunkerweb && \
	mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
	mkdir -p /data/cache/letsencrypt && ln -s /data/cache/letsencrypt /etc/letsencrypt && \
	mkdir -p /data/www && ln -s /data/www /var/www/html && \
	for dir in $(echo "configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
	for dir in $(echo "configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
	chown -R root:nginx /data && \
	chmod -R 770 /data && \
	chown -R root:nginx /usr/share/bunkerweb /var/cache/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /usr/bin/bwcli && \
	for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type f -exec chmod 0740 {} \; ; done && \
	for dir in $(echo "/usr/share/bunkerweb /etc/bunkerweb") ; do find ${dir} -type d -exec chmod 0750 {} \; ; done && \
	chmod 770 /var/cache/bunkerweb /var/tmp/bunkerweb && \
	chmod 750 /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/gen/main.py /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/entrypoint.sh /usr/bin/bwcli /usr/share/bunkerweb/deps/python/bin/* && \
	chown -R root:nginx /etc/nginx && \
	chmod -R 770 /etc/nginx && \
	rm -f /var/log/nginx/* && \
	mkdir /var/log/letsencrypt /var/lib/letsencrypt && \
	chown root:nginx /var/log/letsencrypt /var/lib/letsencrypt && \
	chmod 770 /var/log/letsencrypt /var/lib/letsencrypt && \
	ln -s /proc/1/fd/2 /var/log/nginx/error.log && \
	ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log && \
	ln -s /proc/1/fd/1 /var/log/nginx/access.log && \
	ln -s /proc/1/fd/1 /var/log/nginx/jobs.log && \
	chmod 660 /usr/share/bunkerweb/INTEGRATION

# Fix CVEs
RUN apk add "openssl>=1.1.1q-r0" "curl>=7.83.1-r5" "git>=2.36.4-r0" "libcurl>=7.83.1-r5" "git>=2.36.5-r0"

VOLUME /data /etc/nginx

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT ["/usr/share/bunkerweb/entrypoint.sh"]
