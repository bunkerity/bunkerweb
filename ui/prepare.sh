#!/bin/sh

# create nginx user
addgroup -g 101 nginx
adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx

# prepare /opt
chown -R root:nginx /opt
find /opt -type f -exec chmod 0740 {} \;
find /opt -type d -exec chmod 0750 {} \;
chmod 750 /opt/bunkerized-nginx/gen/main.py

# prepare /var/log
mkdir /var/log/nginx
chown root:nginx /var/log/nginx
chmod 750 /var/log/nginx
ln -s /proc/1/fd/1 /var/log/nginx/ui.log