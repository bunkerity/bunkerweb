#!/bin/sh

. /opt/scripts/utils.sh

if [ ! -f /etc/nginx/block-proxies.conf ] ; then
	echo "" > /etc/nginx/block-proxies.conf
fi
echo "" > /cache/block-proxies.conf
curl -s "https://iplists.firehol.org/files/firehol_proxies.netset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /cache/block-proxies.conf
	fi
done

cp /cache/block-proxies.conf /etc/nginx/block-proxies.conf
lines="$(wc -l /etc/nginx/block-proxies.conf | cut -d ' ' - f1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] proxies list updated ($lines entries)"
else
	job_log "[BLACKLIST] can't update proxies list"
fi

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after proxies list update"
	else
		job_log "[NGINX] failed nginx reload after proxies list update"
	fi
fi
