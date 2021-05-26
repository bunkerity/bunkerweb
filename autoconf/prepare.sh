#!/bin/sh

# create nginx user
addgroup -g 101 nginx
adduser -h /var/cache/nginx -g nginx -s /sbin/nologin -G nginx -D -H -u 101 nginx

# prepare /opt
chown -R root:nginx /opt
find /opt -type f -exec chmod 0740 {} \;
find /opt -type d -exec chmod 0750 {} \;
chmod ugo+x /opt/entrypoint/* /opt/scripts/*
chmod ugo+x /opt/gen/main.py
chmod 770 /opt
chmod 440 /opt/settings.json

# prepare /var/log
ln -s /proc/1/fd/1 /var/log/jobs.log
mkdir /var/log/letsencrypt
chown nginx:nginx /var/log/letsencrypt
chmod 770 /var/log/letsencrypt

# prepare /etc/letsencrypt
mkdir /etc/letsencrypt
chown root:nginx /etc/letsencrypt
chmod 770 /etc/letsencrypt

# prepare /var/lib/letsencrypt
mkdir /var/lib/letsencrypt
chown root:nginx /var/lib/letsencrypt
chmod 770 /var/lib/letsencrypt

# prepare /cache
mkdir /cache
chown root:nginx /cache
chmod 770 /cache

# prepare /acme-challenge
mkdir /acme-challenge
chown root:nginx /acme-challenge
chmod 770 /acme-challenge

# prepare /etc/crontabs/nginx
chown root:nginx /etc/crontabs/nginx
chmod 440 /etc/crontabs/nginx
