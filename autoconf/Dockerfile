FROM alpine

RUN apk add py3-pip apache2-utils bash && \
    pip3 install docker && \
    mkdir /opt/entrypoint && \
    mkdir -p /opt/confs/site

COPY confs/site/ /opt/confs/site
COPY entrypoint/* /opt/entrypoint/
COPY autoconf/* /opt/entrypoint/
RUN chmod +x /opt/entrypoint/*.py /opt/entrypoint/*.sh

# Fix CVE-2020-1971
RUN apk add "libcrypto1.1>1.1.1g-r0"

VOLUME /etc/nginx

ENTRYPOINT ["/opt/entrypoint/entrypoint.py"]
