#!/bin/sh

# you need to run it before starting bunkerized-nginx to get the first certificate

# edit according to your values
DOMAINS="kakou-corp.fr,*.kakou-corp.fr"
EMAIL="contact@kakou-corp.fr"
SERVICE="mywww"

# ask for the certificate
# don't forget to first edit the cloudflare.ini file
docker run --rm \
       -v "${PWD}/cloudflare.ini:/tmp/cloudflare.ini" \
       -v "${PWD}/letsencrypt:/etc/letsencrypt" \
       certbot/dns-cloudflare \
       certonly \
       --dns-cloudflare \
       --dns-cloudflare-credentials /tmp/cloudflare.ini \
       --dns-cloudflare-propagation-seconds 60 \
       -d "$DOMAINS" \
       --email "$EMAIL" \
       --agree-tos \
       --no-eff-email
if [ $? -ne 0 ] ; then
	echo "error while getting certificate for $DOMAINS"
	exit 1
fi

# fix permissions
chgrp -R 101 "${PWD}/letsencrypt"
chmod -R 750 "${PWD}/letsencrypt"

echo "Certificate for $DOMAINS created !"
