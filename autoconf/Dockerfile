FROM python:3.11-rc-alpine

# Copy python requirements
COPY bw/deps/requirements.txt /opt/bunkerweb/deps/requirements.txt

# Install dependencies
RUN apk add --no-cache --virtual build g++ gcc python3-dev musl-dev libffi-dev openssl-dev cargo && \
    pip install --no-cache-dir --upgrade pip && \
    pip install wheel && \
    mkdir /opt/bunkerweb/deps/python && \
    pip install --no-cache-dir --require-hashes --target /opt/bunkerweb/deps/python -r /opt/bunkerweb/deps/requirements.txt && \
    apk del build

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY autoconf /opt/bunkerweb/autoconf
COPY bw/api /opt/bunkerweb/api
COPY bw/core /opt/bunkerweb/core
COPY bw/settings.json /opt/bunkerweb/settings.json
COPY db /opt/bunkerweb/db
COPY utils /opt/bunkerweb/utils

# Add nginx user, drop bwcli, setup data folders, permissions and logging
RUN apk add --no-cache bash && \
    addgroup -g 101 nginx && \
    adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx && \
    chown -R nginx:nginx /opt/bunkerweb && \
    find /opt/bunkerweb -type f -exec chmod 0740 {} \; && \
    find /opt/bunkerweb -type d -exec chmod 0750 {} \;

VOLUME /data

WORKDIR /opt/bunkerweb/autoconf

USER root:nginx

CMD ["python3", "/opt/bunkerweb/autoconf/main.py"]
