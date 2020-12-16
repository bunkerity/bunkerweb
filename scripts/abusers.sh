#!/bin/sh

. /opt/scripts/utils.sh

if [ ! -f /etc/nginx/block-abusers.conf ] ; then
	echo "" > /etc/nginx/block-abusers.conf
fi
echo "" > /cache/block-abusers.conf
curl -s "https://iplists.firehol.org/files/firehol_abusers_30d.netset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /cache/block-abusers.conf
	fi
done

cp /cache/block-abusers.conf /etc/nginx/block-abusers.conf
lines="$(wc -l /etc/nginx/block-abusers.conf | cut -d ' ' - f1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] abusers list updated ($lines entries)"
else
	job_log "[BLACKLIST] can't update abusers list"
fi

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after abusers list update"
	else
		job_log "[NGINX] failed nginx reload after abusers list update"
	fi
fi
