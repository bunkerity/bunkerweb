#!/bin/sh

function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
}

# check if HTTP enabled
# and disable it temporarily if needed
if grep -q "listen 0.0.0.0:80;" "/etc/nginx/server.conf" ; then
	replace_in_file "/etc/nginx/server.conf" "listen 0.0.0.0:80;" "#listen 0.0.0.0:80;"
	if [ -f /run/nginx/nginx.pid ] ; then
		/usr/sbin/nginx -s reload
		sleep 10
	fi
fi

# ask a new certificate if needed
certbot renew

# enable HTTP again if needed
if grep -q "#listen 0.0.0.0:80;" "/etc/nginx/server.conf" ; then
	replace_in_file "/etc/nginx/server.conf" "#listen 0.0.0.0:80;" "listen 0.0.0.0:80;"
fi

# reload nginx
if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
