FROM nginx:1.20.2-alpine AS builder

# Copy dependencies sources folder
COPY deps /tmp/bunkerweb/deps

# Compile and install dependencies
RUN apk add --no-cache --virtual build bash build autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev && \
	mkdir -p /opt/bunkerweb/deps && \
	chmod +x /tmp/bunkerweb/deps/install.sh && \
	bash /tmp/bunkerweb/deps/install.sh && \
	apk del build

# Copy python requirements
COPY deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build py3-pip gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
	pip install wheel && \
	mkdir /opt/bunkerweb/deps/python && \
	pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
	apk del build

FROM nginx:1.20.2-alpine

# Copy dependencies
COPY --from=builder /opt/bunkerweb /opt/bunkerweb

# Copy files
# can't exclude deps from . so we are copying everything by hand
COPY api /opt/bunkerweb/api
COPY cli /opt/bunkerweb/cli
COPY confs /opt/bunkerweb/confs
COPY core /opt/bunkerweb/core
COPY gen /opt/bunkerweb/gen
COPY helpers /opt/bunkerweb/helpers
COPY job /opt/bunkerweb/job
COPY lua /opt/bunkerweb/lua
COPY misc /opt/bunkerweb/misc
COPY utils /opt/bunkerweb/utils
COPY settings.json /opt/bunkerweb/settings.json
COPY VERSION /opt/bunkerweb/VERSION

# Install runtime dependencies, pypi packages, move bwcli, create data folders and set permissions
RUN apk add --no-cache bash python3 libgcc libstdc++ openssl git && \
	chown root:nginx /opt/bunkerweb/modules && \
	chmod 750 /opt/bunkerweb/modules && \
	chmod 740 /opt/bunkerweb/modules/*.so && \
	cp /opt/bunkerweb/helpers/bwcli /usr/local/bin && \
	mkdir /opt/bunkerweb/configs && \
	for dir in $(echo "cache configs configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs letsencrypt plugins www") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
	chown -R root:nginx /data && \
	chmod -R 770 /data && \
	mkdir /opt/bunkerweb/tmp && \
	chown -R root:nginx /opt/bunkerweb && \
	find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
	find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
	chmod 770 /opt/bunkerweb/cache /opt/bunkerweb/tmp && \
	chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/job/main.py /opt/bunkerweb/cli/main.py /opt/bunkerweb/helpers/*.sh /usr/local/bin/bwcli /opt/bunkerweb/deps/python/bin/* && \
	find /opt/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
	chown root:nginx /usr/local/bin/bwcli && \
	chown -R nginx:nginx /etc/nginx && \
	ln -s /data/letsencrypt /etc/letsencrypt && \
	mkdir /var/log/letsencrypt /var/lib/letsencrypt && \
	chown root:nginx /var/log/letsencrypt /var/lib/letsencrypt && \
	chmod 770 /var/log/letsencrypt /var/lib/letsencrypt && \
	chown -R root:nginx /etc/nginx && \
	chmod -R 770 /etc/nginx && \
	rm -f /var/log/nginx/* && \
	ln -s /proc/1/fd/2 /var/log/nginx/error.log && \
	ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log && \
	ln -s /proc/1/fd/1 /var/log/nginx/access.log && \
	ln -s /proc/1/fd/1 /var/log/nginx/jobs.log && \
	ln -s /proc/1/fd/1 /var/log/letsencrypt/letsencrypt.log

# Fix CVE-2022-27405 and CVE-2022-27406
RUN apk add "freetype>=2.10.4-r3"

VOLUME /data

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /opt/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT ["/opt/bunkerweb/helpers/entrypoint.sh"]
