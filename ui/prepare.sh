#!/bin/sh

# create nginx user
addgroup -g 101 nginx
adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx

# prepare /opt
chown -R root:nginx /opt
find /opt -type f -exec chmod 0740 {} \;
find /opt -type d -exec chmod 0750 {} \;
chmod ugo+x /opt/entrypoint/*
chmod ugo+x /opt/gen/main.py
chmod 770 /opt
chmod 440 /opt/settings.json