FROM nginx:1.20.1-alpine AS builder

FROM alpine

COPY --from=builder /etc/nginx/ /opt/confs/nginx

COPY autoconf/dependencies.sh /tmp
RUN chmod +x /tmp/dependencies.sh && \
    /tmp/dependencies.sh && \
    rm -f /tmp/dependencies.sh

COPY gen/ /opt/gen
COPY entrypoint/ /opt/entrypoint
COPY confs/global/ /opt/confs/global
COPY confs/site/ /opt/confs/site
COPY scripts/ /opt/scripts
COPY settings.json /opt
COPY misc/cron /etc/crontabs/nginx
COPY autoconf/* /opt/entrypoint/

COPY autoconf/prepare.sh /tmp
RUN chmod +x /tmp/prepare.sh && \
    /tmp/prepare.sh && \
    rm -f /tmp/prepare.sh

ENTRYPOINT ["/opt/entrypoint/entrypoint.sh"]
