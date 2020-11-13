#!/bin/sh

function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
}

# disable HTTP
servers="$(find /etc/nginx -name server.conf)"
for f in $servers ; do
	replace_in_file "$f" "listen" "#listen"
done
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
	sleep 10
fi

# ask a new certificate if needed
certbot renew

# enable HTTP again
for f in $servers ; do
	replace_in_file "$f" "#listen" "listen"
done

chown -R root:nginx /etc/letsencrypt
chmod -R 740 /etc/letsencrypt
find /etc/letsencrypt -type d -exec chmod 750 {} \;

# reload nginx
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
