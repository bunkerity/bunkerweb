#!/bin/sh

echo "" > /etc/nginx/block-abusers.conf
curl -s "https://iplists.firehol.org/files/firehol_abusers_30d.netset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /etc/nginx/block-abusers.conf
	fi
done
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
