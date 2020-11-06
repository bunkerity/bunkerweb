#!/bin/sh

function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
}

# check if HTTP enabled
# and disable it temporarily if needed
if grep -q "listen" "/etc/nginx/server.conf" ; then
	replace_in_file "/etc/nginx/server.conf" "listen" "#listen"
	if [ -f /tmp/nginx.pid ] ; then
		/usr/sbin/nginx -s reload
		sleep 10
	fi
fi

# ask a new certificate if needed
certbot renew

# enable HTTP again if needed
if grep -q "#listen" "/etc/nginx/server.conf" ; then
	replace_in_file "/etc/nginx/server.conf" "#listen" "listen"
fi

chown -R root:nginx /etc/letsencrypt
chmod -R 740 /etc/letsencrypt
find /etc/letsencrypt -type d -exec chmod 750 {} \;

# reload nginx
if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
