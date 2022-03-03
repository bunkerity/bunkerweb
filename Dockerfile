FROM nginx:1.20.2-alpine

COPY . /tmp/bunkerized-nginx-docker
COPY helpers/install.sh /tmp/install.sh
RUN apk --no-cache add bash && \
    chmod +x /tmp/install.sh && \
    /tmp/install.sh && \
    rm -f /tmp/install.sh

COPY helpers/docker.sh /tmp/docker.sh
RUN chmod +x /tmp/docker.sh && \
    /tmp/docker.sh && \
    rm -f /tmp/docker.sh

# Fix CVE-2021-22945, CVE-2021-22946, CVE-2021-22947 and CVE-2021-40528
RUN apk add "curl>=7.79.0-r0" "libgcrypt>=1.8.8-r1"

VOLUME /www /http-confs /server-confs /modsec-confs /modsec-crs-confs /cache /pre-server-confs /acme-challenge /plugins

EXPOSE 8080/tcp 8443/tcp

USER nginx:nginx

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD [ -f /tmp/nginx.pid ] || [ -f /tmp/nginx-temp.pid ] || exit 1

ENTRYPOINT ["/opt/bunkerized-nginx/entrypoint/entrypoint.sh"]
