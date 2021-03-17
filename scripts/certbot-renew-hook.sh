#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

job_log "[CERTBOT] certificates have been renewed"

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload > /dev/null 2>&1"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="echo reload > /tmp/autoconf.sock"
fi

# reload nginx
if [ "$RELOAD" != "" ] ; then
	$RELOAD
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after certbot renew"
	else
		job_log "[NGINX] failed nginx reload after certbot renew"
	fi
fi
