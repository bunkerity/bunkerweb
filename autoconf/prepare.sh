#!/bin/sh

# create nginx user
addgroup -g 101 nginx
adduser -h /var/cache/nginx -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx

# prepare /opt
chown root:nginx /opt
chmod 750 /opt

# prepare /opt/bunkerized-nginx
chown -R root:nginx /opt/bunkerized-nginx
find /opt/bunkerized-nginx -type f -exec chmod 0740 {} \;
find /opt/bunkerized-nginx -type d -exec chmod 0750 {} \;
chmod ugo+x /opt/bunkerized-nginx/entrypoint/* /opt/bunkerized-nginx/scripts/*
chmod ugo+x /opt/bunkerized-nginx/gen/main.py
chmod ugo+x /opt/bunkerized-nginx/jobs/main.py
chmod ugo+x /opt/bunkerized-nginx/jobs/reload.py
chmod ugo+x /opt/bunkerized-nginx/jobs/certbot-*.py
chmod 770 /opt/bunkerized-nginx
chmod 440 /opt/bunkerized-nginx/settings.json

# prepare /var/log
mkdir /var/log/nginx
chown root:nginx /var/log/nginx
chmod 770 /var/log/nginx
ln -s /proc/1/fd/1 /var/log/nginx/jobs.log
mkdir /var/log/letsencrypt
chown nginx:nginx /var/log/letsencrypt
chmod 770 /var/log/letsencrypt

# prepare /etc/nginx
mkdir /etc/nginx
chown root:nginx /etc/nginx
chmod 770 /etc/nginx

# prepare /etc/letsencrypt
mkdir /etc/letsencrypt
chown root:nginx /etc/letsencrypt
chmod 770 /etc/letsencrypt

# prepare /var/lib/letsencrypt
mkdir /var/lib/letsencrypt
chown root:nginx /var/lib/letsencrypt
chmod 770 /var/lib/letsencrypt

# prepare /opt/bunkerized-nginx/cache
ln -s /cache /opt/bunkerized-nginx/cache
mkdir /cache
chown root:nginx /cache
chmod 770 /cache

# prepare /acme-challenge
ln -s /acme-challenge /opt/bunkerized-nginx/acme-challenge
mkdir -p /acme-challenge/.well-known/acme-challenge
chown -R root:nginx /acme-challenge
chmod -R 770 /acme-challenge

# prepare /http-confs
ln -s /http-confs /opt/bunkerized-nginx/http-confs
mkdir /http-confs
chown root:nginx /http-confs
chmod 770 /http-confs

# prepare /server-confs
ln -s /server-confs /opt/bunkerized-nginx/server-confs
mkdir /server-confs
chown root:nginx /server-confs
chmod 770 /server-confs

# prepare /modsec-confs
ln -s /modsec-confs /opt/bunkerized-nginx/modsec-confs
mkdir /modsec-confs
chown root:nginx /modsec-confs
chmod 770 /modsec-confs

# prepare /modsec-crs-confs
ln -s /modsec-crs-confs /opt/bunkerized-nginx/modsec-crs-confs
mkdir /modsec-crs-confs
chown root:nginx /modsec-crs-confs
chmod 770 /modsec-crs-confs
