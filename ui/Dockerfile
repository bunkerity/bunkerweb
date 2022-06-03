FROM python:3-alpine AS builder

# Copy python requirements
COPY deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install python requirements
RUN apk add --no-cache --virtual build gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    mkdir /opt/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
    apk del build

FROM python:3-alpine

COPY --from=builder /opt/bunkerweb/deps/python /opt/bunkerweb/deps/python

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY api /opt/bunkerweb/api
COPY confs /opt/bunkerweb/confs
COPY core /opt/bunkerweb/core
COPY gen /opt/bunkerweb/gen
COPY utils /opt/bunkerweb/utils
COPY settings.json /opt/bunkerweb/settings.json
COPY VERSION /opt/bunkerweb/VERSION
COPY ui/requirements.txt /opt/bunkerweb/ui/requirements.txt

# Install UI requirements
RUN apk add --no-cache --virtual build gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    pip install -r /opt/bunkerweb/ui/requirements.txt && \
    apk del build

COPY ui /opt/bunkerweb/ui

# Add nginx user
RUN addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
    apk add --no-cache bash file && \
    for dir in $(echo "cache configs letsencrypt plugins www") ; do ln -s "/data/${dir}" "/opt/bunkerweb/${dir}" ; done && \
    mkdir /opt/bunkerweb/tmp && \
    chown -R root:nginx /opt/bunkerweb && \
    find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /opt/bunkerweb -type d -exec chmod 0750 {} \; && \
    chmod 770 /opt/bunkerweb/tmp && \
    chmod 750 /opt/bunkerweb/gen/main.py /opt/bunkerweb/deps/python/bin/* && \  
    mkdir /etc/nginx && \
    chown -R nginx:nginx /etc/nginx && \
    chmod -R 770 /etc/nginx && \
    ln -s /usr/local/bin/python /usr/bin/python3

VOLUME /data /etc/nginx

EXPOSE 5000

WORKDIR /opt/bunkerweb/ui
USER nginx:nginx
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP "main.py"
ENV FLASK_ENV production
CMD ["flask", "run", "--host=0.0.0.0", "--port=7000"]
