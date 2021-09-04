#!/bin/bash

. /opt/bunkerized-nginx/entrypoint/utils.sh

echo $CERTBOT_VALIDATION > /opt/bunkerized-nginx/acme-challenge/.well-known/acme-challenge/$CERTBOT_TOKEN

if [ -S "/tmp/autoconf.sock" ] ; then
	echo -e "lock\nacme\nunlock" | socat UNIX-CONNECT:/tmp/autoconf.sock -
fi
