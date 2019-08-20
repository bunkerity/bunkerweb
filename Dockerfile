FROM alpine

COPY compile.sh /tmp/compile.sh
RUN chmod +x /tmp/compile.sh && \
    /tmp/compile.sh && \
    rm -rf /tmp/*

COPY entrypoint.sh /opt/entrypoint.sh
COPY confs/ /opt/confs
COPY scripts/ /opt/scripts

RUN apk --no-cache add php7-fpm certbot libstdc++ libmaxminddb geoip pcre yajl && \
    chmod +x /opt/entrypoint.sh /opt/scripts/* && \
    mkdir /www && \
    adduser -h /dev/null -g '' -s /sbin/nologin -D -H nginx

VOLUME /www

EXPOSE 80
EXPOSE 443

ENTRYPOINT ["/opt/entrypoint.sh"]
