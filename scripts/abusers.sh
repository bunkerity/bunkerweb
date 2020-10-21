#!/bin/sh

echo "" > /etc/nginx/block-abusers.conf
curl -s "https://iplists.firehol.org/files/firehol_abusers_30d.netset" | grep -v "^\#.*" |
while read entry ; do
	echo "deny ${entry};" >> /etc/nginx/block-abusers.conf
done
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
