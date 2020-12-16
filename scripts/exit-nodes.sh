#!/bin/sh

. /opt/scripts/utils.sh

if [ ! -f /etc/nginx/block-tor-exit-node.conf ] ; then
	echo "" > /etc/nginx/block-tor-exit-node.conf
fi
echo "" > /cache/block-tor-exit-node.conf
curl -s "https://iplists.firehol.org/files/tor_exits.ipset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /cache/block-tor-exit-node.conf
	fi
done

cp /cache/block-tor-exit-node.conf /etc/nginx/block-tor-exit-node.conf
lines="$(wc -l /etc/nginx/block-tor-exit-node.conf | cut -d ' ' - f1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] TOR exit node list updated ($lines entries)"
else
	job_log "[BLACKLIST] can't update TOR exit node list"
fi

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after TOR exit node list update"
	else
		job_log "[NGINX] failed nginx reload after TOR exit node list update"
	fi
fi
