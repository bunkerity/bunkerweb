#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

# copy old conf to cache
cp /etc/nginx/block-abusers.conf /cache

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload > /dev/null 2>&1"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# generate the new conf
curl -s "https://iplists.firehol.org/files/firehol_abusers_30d.netset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /tmp/block-abusers.conf
	fi
done

# check if we have at least 1 line
lines="$(wc -l /tmp/block-abusers.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] abusers list updated ($lines entries)"
	# reload nginx with the new config
	mv /tmp/block-abusers.conf /etc/nginx/block-abusers.conf
	if [ "$RELOAD" != "" ] ; then
		$RELOAD
		# new config is ok : save it in the cache
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/block-abusers.conf /cache
			job_log "[NGINX] successfull nginx reload after abusers list update"
		else
			job_log "[NGINX] failed nginx reload after abusers list update fallback to old list"
			cp /cache/block-abusers.conf /etc/nginx
			$RELOAD
		fi
	else
		cp /etc/nginx/block-abusers.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update abusers list"
fi

rm -f /tmp/block-abusers.conf 2> /dev/null

