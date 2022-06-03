FROM python:3.10-alpine

COPY . /opt/bunkerweb

RUN addgroup -g 101 nginx && \
    adduser -h /opt/bunkerweb -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
	chown -R root:nginx /opt && \
	find /opt -type f -exec chmod 0740 {} \; && \
	find /opt -type d -exec chmod 0750 {} \; && \
	chmod 750 /opt/bunkerweb/gen/main.py && \
	pip3 install -r /opt/bunkerweb/gen/requirements.txt && \
	mkdir /etc/nginx /opt/bunkerweb/plugins && \
	chown root:nginx /etc/nginx /opt/bunkerweb/plugins && \
	chmod 770 /etc/nginx /opt/bunkerweb/plugins

WORKDIR /opt/bunkerweb/gen

USER nginx:nginx

VOLUME /etc/nginx /opt/bunkerweb/plugins

ENTRYPOINT ["python3", "/opt/bunkerweb/gen/main.py"]