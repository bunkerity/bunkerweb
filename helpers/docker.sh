#!/bin/sh

# prepare /www
mkdir /www
chown -R root:nginx /www
chmod -R 770 /www

# prepare /acme-challenge
mkdir /acme-challenge
chown root:nginx /acme-challenge
chmod 770 /acme-challenge

# prepare /cache
mkdir /cache
chown root:nginx /cache
chmod 770 /cache

# prepare /plugins
mkdir /plugins
chown root:nginx /plugins
chmod 770 /plugins

# prepare symlinks
folders="www http-confs server-confs modsec-confs modsec-crs-confs cache pre-server-confs acme-challenge plugins"
for folder in $folders ; do
	if [ -e "/opt/bunkerized-nginx/$folder" ] ; then
		rm -rf "/opt/bunkerized-nginx/$folder"
	fi
	ln -s "/$folder" "/opt/bunkerized-nginx/$folder"
done

# prepare /var/log
rm -f /var/log/nginx/*
ln -s /proc/1/fd/2 /var/log/nginx/error.log
ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log
ln -s /proc/1/fd/1 /var/log/nginx/access.log
ln -s /proc/1/fd/1 /var/log/nginx/jobs.log
