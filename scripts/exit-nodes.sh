#!/bin/sh

echo "" > /etc/nginx/block-tor-exit-node.conf
curl -s "https://iplists.firehol.org/files/tor_exits.ipset" | grep -v "^\#.*" |
while read entry ; do
	echo "deny ${entry};" >> /etc/nginx/block-tor-exit-node.conf
done
if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
