FROM nginx:1.20.1-alpine

COPY helpers/dependencies.sh /tmp/dependencies.sh && \
     apk add --no-cache bash && \
     /tmp/dependencies.sh && \
     rm -f /tmp/dependencies.sh

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

# Fix CVE-2021-22901, CVE-2021-22898 and CVE-2021-22897
RUN apk add "curl>=7.77.0-r0"

VOLUME /www /http-confs /server-confs /modsec-confs /modsec-crs-confs /cache /pre-server-confs /acme-challenge /plugins

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD [ -f /tmp/nginx.pid ] || exit 1

ENTRYPOINT ["/opt/entrypoint/entrypoint.sh"]
