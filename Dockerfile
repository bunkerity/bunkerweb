FROM nginx:1.20.1-alpine

COPY nginx-keys/ /tmp/nginx-keys
COPY compile.sh /tmp/compile.sh
RUN chmod +x /tmp/compile.sh && \
    /tmp/compile.sh && \
    rm -rf /tmp/*

COPY dependencies.sh /tmp/dependencies.sh
RUN chmod +x /tmp/dependencies.sh && \
    /tmp/dependencies.sh && \
    rm -rf /tmp/dependencies.sh

COPY gen/ /opt/gen
COPY entrypoint/ /opt/entrypoint
COPY confs/ /opt/confs
COPY scripts/ /opt/scripts
COPY lua/ /usr/local/lib/lua
COPY antibot/ /antibot
COPY defaults/ /defaults
COPY settings.json /opt
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

ENTRYPOINT ["/opt/entrypoint/entrypoint.sh"]
