FROM nginx:1.20.1-alpine

COPY helpers/dependencies.sh /tmp/dependencies.sh
RUN apk add --no-cache bash && \
    chmod +x /tmp/dependencies.sh && \
    /tmp/dependencies.sh && \
    rm -f /tmp/dependencies.sh

RUN apk add --no-cache certbot bash libmaxminddb libgcc lua yajl libstdc++ openssl py3-pip && \
    pip3 install jinja2

COPY gen/ /opt/bunkerized-nginx/gen
COPY entrypoint/ /opt/bunkerized-nginx/entrypoint
COPY confs/ /opt/bunkerized-nginx/confs
COPY scripts/ /opt/bunkerized-nginx/scripts
COPY lua/ /usr/local/lib/lua
COPY antibot/ /opt/bunkerized-nginx/antibot
COPY defaults/ /opt/bunkerized-nginx/defaults
COPY settings.json /opt/bunkerized-nginx
COPY misc/cron /etc/crontabs/nginx

COPY prepare.sh /tmp/prepare.sh
RUN chmod +x /tmp/prepare.sh && \
    /tmp/prepare.sh && \
    rm -f /tmp/prepare.sh

# Fix CVE-2021-22901, CVE-2021-22898, CVE-2021-22897 and CVE-2021-33560
RUN apk add "curl>=7.77.0-r0" "libgcrypt>=1.8.8-r0"

VOLUME /www /http-confs /server-confs /modsec-confs /modsec-crs-confs /cache /pre-server-confs /acme-challenge /plugins

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD [ -f /tmp/nginx.pid ] || exit 1

ENTRYPOINT ["/opt/bunkerized-nginx/entrypoint/entrypoint.sh"]
