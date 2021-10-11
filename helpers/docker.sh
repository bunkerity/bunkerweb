#!/bin/sh

# prepare folders
folders="www http-confs server-confs modsec-confs modsec-crs-confs cache pre-server-confs acme-challenge plugins"
for folder in $folders ; do
	if [ -e "/opt/bunkerized-nginx/${folder}" ] ; then
		rm -rf "/opt/bunkerized-nginx/${folder}"
	fi
	mkdir "/${folder}"
	chown root:nginx "/${folder}"
	chmod 770 "/${folder}"
	ln -s "/$folder" "/opt/bunkerized-nginx/$folder"
done
mkdir -p /acme-challenge/.well-known/acme-challenge
chown -R root:nginx /acme-challenge
chmod 770 /acme-challenge

# prepare /var/log
rm -f /var/log/nginx/*
ln -s /proc/1/fd/2 /var/log/nginx/error.log
ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log
ln -s /proc/1/fd/1 /var/log/nginx/access.log
ln -s /proc/1/fd/1 /var/log/nginx/jobs.log
