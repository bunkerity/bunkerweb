#!/bin/sh

function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
}

# check if HTTP to HTTPS is enabled
# then disable it temporarily
if grep -q "include /etc/nginx/redirect-http-to-https.conf;" "/etc/nginx/nginx.conf" ; then
	replace_in_file "/etc/nginx/nginx.conf" "include /etc/nginx/redirect-http-to-https.conf;" "#include /etc/nginx/redirect-http-to-https.conf;"
	if [ -f /run/nginx/nginx.pid ] ; then
		/usr/sbin/nginx -s reload
	fi
fi

# ask a new certificate if needed
certbot renew

# enable HTTP to HTTPS if needed
if grep -q "#include /etc/nginx/redirect-http-to-https.conf;" "/etc/nginx/nginx.conf" ; then
	replace_in_file "/etc/nginx/nginx.conf" "#include /etc/nginx/redirect-http-to-https.conf;" "include /etc/nginx/redirect-http-to-https.conf;"
fi

# reload nginx
if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
