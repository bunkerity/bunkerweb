#!/bin/sh

# you need to run it before starting bunkerized-nginx
# since it's manual there is no auto renew, you need to run it again before it expires

DOMAIN="*.website.com"
SERVICE="mywww"

# ask for wildcard certificate
# it's interactive and you will need to add a DNS entry
docker run --rm -it -v "${PWD}/letsencrypt:/etc/letsencrypt" certbot/certbot certonly --manual -d $DOMAIN --agree-tos
if [ $? -ne 0 ] ; then
	echo "error while getting certificate for $DOMAIN"
	exit 1
fi

# fix permissions
chown -R 101:101 "${PWD}/letsencrypt"

# reload nginx if it's already running (in case of a "renew")
if [ -z `docker-compose ps -q $SERVICE` ] || [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q $SERVICE)` ]; then
	echo "bunkerized-nginx is not running, skipping nginx reload"
else
	echo "bunkerized-nginx is running, sending reload order"
	docker-compose exec $SERVICE nginx -s reload
fi
