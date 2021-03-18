FROM alpine

RUN apk add py3-pip apache2-utils bash && \
    pip3 install docker flask && \
    mkdir /opt/entrypoint && \
    mkdir -p /opt/confs/site && \
    addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /sbin/nologin -G nginx -D -H -u 101 nginx && \
    mkdir /etc/nginx && \
    chown root:nginx /etc/nginx && \
    chmod 770 /etc/nginx
    

COPY confs/site/ /opt/confs/site
COPY entrypoint/* /opt/entrypoint/
COPY ui/ /opt/entrypoint/
RUN chmod +x /opt/entrypoint/*.py /opt/entrypoint/*.sh

EXPOSE 5000

WORKDIR /opt/entrypoint
ENV FLASK_APP entrypoint.py
ENTRYPOINT ["/usr/bin/python3", "-m", "flask", "run", "--host=0.0.0.0"]
