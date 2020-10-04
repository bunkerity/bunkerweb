#!/bin/sh

echo "" > /etc/nginx/block-proxies.conf
curl -s "https://iplists.firehol.org/files/firehol_proxies.netset" | grep -v "^\#.*" |
while read entry ; do
	echo "deny ${entry};" >> /etc/nginx/block-proxies.conf
done
if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
