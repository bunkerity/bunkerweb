FROM alpine

RUN apk add py3-pip && \
    pip3 install docker

COPY *.py /opt/
RUN chmod +x /opt/entrypoint.py

VOLUME /etc/nginx

ENTRYPOINT ["/opt/entrypoint.py"]
