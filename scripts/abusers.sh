#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

if [ $(grep "^SWARM_MODE=yes$" /etc/nginx/global.env) != "" ] && [ -f /usr/sbin/nginx ] ; then
	exit 0
fi

if [ "$(has_value BLOCK_ABUSERS yes)" = "" ] ; then
	exit 0
fi

# copy old conf to cache
cp /etc/nginx/abusers.list /cache

# generate the new conf
curl -s "https://iplists.firehol.org/files/firehol_abusers_30d.netset" | \
	grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$" > /tmp/abusers.list

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# check if we have at least 1 line
lines="$(wc -l /tmp/abusers.list | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] abusers list updated ($lines entries)"
	# reload nginx with the new config
	mv /tmp/abusers.list /etc/nginx/abusers.list
	if [ "$RELOAD" != "" ] ; then
		$RELOAD > /dev/null 2>&1
		# new config is ok : save it in the cache
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/abusers.list /cache
			job_log "[NGINX] successfull nginx reload after abusers list update"
		else
			job_log "[NGINX] failed nginx reload after abusers list update fallback to old list"
			cp /cache/abusers.list /etc/nginx
			$RELOAD > /dev/null 2>&1
		fi
	else
		cp /etc/nginx/abusers.list /cache
	fi
else
	job_log "[BLACKLIST] can't update abusers list"
fi

rm -f /tmp/abusers.list 2> /dev/null

