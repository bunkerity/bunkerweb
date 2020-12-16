#!/bin/sh

# load some functions
. /opt/scripts/utils.sh

# copy old conf to cache
cp /etc/nginx/block-tor-exit-node.conf /cache

# generate the new conf
curl -s "https://iplists.firehol.org/files/tor_exits.ipset" | grep -v "^\#.*" |
while read entry ; do
	check=$(echo $entry | grep -E "^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$")
	if [ "$check" != "" ] ; then
		echo "deny ${entry};" >> /tmp/block-tor-exit-node.conf
	fi
done

# check if we have at least 1 line
lines="$(wc -l /tmp/block-tor-exit-node.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	job_log "[BLACKLIST] TOR exit node list updated ($lines entries)"
	# reload nginx with the new config
	mv /tmp/block-tor-exit-node.conf /etc/nginx/block-tor-exit-node.conf
	if [ -f /tmp/nginx.pid ] ; then
		/usr/sbin/nginx -s reload > /dev/null 2>&1
		# new config is ok : save it in the cache
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/block-tor-exit-node.conf /cache
			job_log "[NGINX] successfull nginx reload after TOR exit node list update"
		else
			job_log "[NGINX] failed nginx reload after TOR exit node list update fallback to old list"
			cp /cache/block-tor-exit-node.conf /etc/nginx
			/usr/sbin/nginx -s reload > /dev/null 2>&1
		fi
	else
		cp /etc/nginx/block-tor-exit-node.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update TOR exit node list"
fi

rm -f /tmp/block-tor-exit-node.conf 2> /dev/null

