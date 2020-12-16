#!/bin/sh

. /opt/scripts/utils.sh

job_log "[CERTBOT] certificates have been renewed"

# fix rights
chown -R root:nginx /etc/letsencrypt
chmod -R 740 /etc/letsencrypt
find /etc/letsencrypt -type d -exec chmod 750 {} \;

# reload nginx
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after certbot renew"
	else
		job_log "[NGINX] failed nginx reload after certbot renew"
	fi
fi
