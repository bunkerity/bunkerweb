#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

job_log "[CERTBOT] certificates have been renewed"

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# reload nginx
if [ "$RELOAD" != "" ] ; then
	$RELOAD > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after certbot renew"
	else
		job_log "[NGINX] failed nginx reload after certbot renew"
	fi
fi
