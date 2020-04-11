#!/bin/sh

BLACKLIST=$(curl -s "https://iplists.firehol.org/files/tor_exits.ipset")
DATA=""
for ip in $BLACKLIST ; do
	DATA="${DATA}deny ${ip};\n"
done
echo $DATA > /etc/nginx/block-tor-exit-node.conf
if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
