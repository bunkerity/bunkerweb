#!/bin/sh

# you should add it to your crontab like :
# 0 0 * * * cd /your/folder && ./certbot-renew.sh

# edit with your service name
SERVICE="mywww"

# ask for the renew
# don't forget to first edit the cloudflare.ini file
docker run --rm \
       -v "${PWD}/cloudflare.ini:/tmp/cloudflare.ini" \
       -v "${PWD}/letsencrypt:/etc/letsencrypt" \
       certbot/dns-cloudflare \
       renew
if [ $? -ne 0 ] ; then
	echo "error while getting certificate for $DOMAINS"
	exit 1
fi

# fix permissions
chgrp -R 101 "${PWD}/letsencrypt"
chmod -R 750 "${PWD}/letsencrypt"

# reload bunkerized-nginx
docker-compose kill -s SIGHUP mywww

echo "Certificate(s) renewed (if needed) !"
