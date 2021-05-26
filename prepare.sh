#!/bin/sh

# prepare /www
mkdir /www
chown -R root:nginx /www
chmod -R 770 /www

# prepare /opt
chown -R root:nginx /opt
find /opt -type f -exec chmod 0740 {} \;
find /opt -type d -exec chmod 0750 {} \;
chmod ugo+x /opt/entrypoint/* /opt/scripts/*
chmod ugo+x /opt/gen/main.py
chmod 770 /opt
chmod 440 /opt/settings.json

# prepare /etc/nginx
for file in $(ls /etc/nginx) ; do
	if [ -f /etc/nginx/$file ] && [ ! -f /opt/confs/global/$file ] ; then
		cp /etc/nginx/$file /opt/confs/global
	fi
done
chown -R root:nginx /etc/nginx
chmod -R 770 /etc/nginx

# prepare /var/log
rm -f /var/log/nginx/*
chown root:nginx /var/log/nginx
chmod -R 770 /var/log/nginx
ln -s /proc/1/fd/2 /var/log/nginx/error.log
ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log
ln -s /proc/1/fd/1 /var/log/access.log
ln -s /proc/1/fd/2 /var/log/error.log
ln -s /proc/1/fd/1 /var/log/jobs.log
mkdir /var/log/letsencrypt
chown nginx:nginx /var/log/letsencrypt
chmod 770 /var/log/letsencrypt

# prepare /acme-challenge
mkdir /acme-challenge
chown root:nginx /acme-challenge
chmod 770 /acme-challenge

# prepare /etc/letsencrypt
mkdir /etc/letsencrypt
chown root:nginx /etc/letsencrypt
chmod 770 /etc/letsencrypt

# prepare /var/lib/letsencrypt
mkdir /var/lib/letsencrypt
chown root:nginx /var/lib/letsencrypt
chmod 770 /var/lib/letsencrypt

# prepare /usr/local/lib/lua
chown -R root:nginx /usr/local/lib/lua
chmod 770 /usr/local/lib/lua
find /usr/local/lib/lua -type f -name "*.lua" -exec chmod 0760 {} \;
find /usr/local/lib/lua -type d -exec chmod 0770 {} \;

# prepare /cache
mkdir /cache
chown root:nginx /cache
chmod 770 /cache

# prepare /etc/crontabs/nginx
chown root:nginx /etc/crontabs/nginx
chmod 440 /etc/crontabs/nginx
