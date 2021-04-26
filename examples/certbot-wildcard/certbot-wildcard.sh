#!/bin/sh

# you need to run it before starting bunkerized-nginx
# since it's manual there is no auto renew, you need to run it again before it expires

# ask for wildcard certificate
# it's interactive and you will need to add a DNS entry
docker run --rm -it -v "${PWD}/letsencrypt:/etc/letsencrypt" certbot/certbot certonly --manual -d *.website.com --agree-tos --no-bootstrap

# fix permissions
chown -R 101:101 "${PWD}/letsencrypt/live"

# reload nginx if it's already running (in case of a "renew")
if [ -z `docker-compose ps -q mywww` ] || [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q mywww)` ]; then
	echo "bunkerized-nginx is not running, skipping nginx reload"
else
	echo "bunkerized-nginx is running, sending reload order"
	docker-compose exec mywww nginx -s reload
fi
