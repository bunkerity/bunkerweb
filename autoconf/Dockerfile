FROM alpine

COPY autoconf/dependencies.sh /tmp
RUN chmod +x /tmp/dependencies.sh && \
    /tmp/dependencies.sh && \
    rm -f /tmp/dependencies.sh && \
    mkdir /opt/bunkerized-nginx

COPY gen/ /opt/bunkerized-nginx/gen
COPY entrypoint/ /opt/bunkerized-nginx/entrypoint
COPY confs/global/ /opt/bunkerized-nginx/confs/global
COPY confs/site/ /opt/bunkerized-nginx/confs/site
COPY scripts/ /opt/bunkerized-nginx/scripts
COPY settings.json /opt/bunkerized-nginx/
COPY misc/cron /etc/crontabs/nginx
COPY autoconf/* /opt/bunkerized-nginx/entrypoint/

COPY autoconf/prepare.sh /tmp
RUN chmod +x /tmp/prepare.sh && \
    /tmp/prepare.sh && \
    rm -f /tmp/prepare.sh

ENTRYPOINT ["/opt/bunkerized-nginx/entrypoint/entrypoint.sh"]
