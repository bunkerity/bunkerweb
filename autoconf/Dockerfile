FROM alpine

RUN apk add py3-pip apache2-utils bash certbot curl logrotate && \
    pip3 install docker && \
    mkdir /opt/entrypoint && \
    mkdir -p /opt/confs/site && \
    mkdir -p /opt/confs/global

COPY confs/site/ /opt/confs/site
COPY confs/global/ /opt/confs/global
COPY entrypoint/* /opt/entrypoint/
COPY autoconf/* /opt/entrypoint/
RUN chmod +x /opt/entrypoint/*.py /opt/entrypoint/*.sh

VOLUME /etc/nginx /etc/letsencrypt

ENTRYPOINT ["/opt/entrypoint/entrypoint.sh"]
