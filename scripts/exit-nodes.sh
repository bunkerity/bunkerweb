#!/bin/sh

echo "" > /etc/nginx/block-tor-exit-node.conf
curl -s "https://iplists.firehol.org/files/tor_exits.ipset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /etc/nginx/block-tor-exit-node.conf
	fi
done
cp /etc/nginx/block-tor-exit-node.conf /cache
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
fi
