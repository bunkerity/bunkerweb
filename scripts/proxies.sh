#!/bin/sh

# load some functions
. /opt/scripts/utils.sh

# copy old conf to cache
cp /etc/nginx/block-proxies.conf /cache

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload > /dev/null 2>&1"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# generate the new conf
curl -s "https://iplists.firehol.org/files/firehol_proxies.netset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /tmp/block-proxies.conf
	fi
done

# check if we have at least 1 line
lines="$(wc -l /tmp/block-proxies.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] proxies list updated ($lines entries)"
	# reload nginx with the new config
	mv /tmp/block-proxies.conf /etc/nginx/block-proxies.conf
	if [ "$RELOAD" != "" ] ; then
		$RELOAD
		# new config is ok : save it in the cache
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/block-proxies.conf /cache
			job_log "[NGINX] successfull nginx reload after proxies list update"
		else
			job_log "[NGINX] failed nginx reload after proxies list update fallback to old list"
			cp /cache/block-proxies.conf /etc/nginx
			$RELOAD
		fi
	else
		cp /etc/nginx/block-proxies.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update proxies list"
fi

rm -f /tmp/block-proxies.conf 2> /dev/null

