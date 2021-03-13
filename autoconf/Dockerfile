FROM nginx:stable-alpine AS builder

FROM alpine

COPY --from=builder /etc/nginx/ /opt/confs/nginx

RUN apk add py3-pip apache2-utils bash certbot curl logrotate openssl && \
    pip3 install docker requests && \
    mkdir /opt/entrypoint && \
    mkdir -p /opt/confs/site && \
    mkdir -p /opt/confs/global && \
    addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /sbin/nologin -G nginx -D -H -u 101 nginx

COPY confs/site/ /opt/confs/site
COPY confs/global/ /opt/confs/global
COPY entrypoint/* /opt/entrypoint/
COPY autoconf/* /opt/entrypoint/
RUN chmod +x /opt/entrypoint/*.py /opt/entrypoint/*.sh

ENTRYPOINT ["/opt/entrypoint/entrypoint.sh"]
