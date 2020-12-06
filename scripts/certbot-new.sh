#!/bin/sh

# generate certificate
certbot certonly --webroot -w /acme-challenge -n -d "$1" --email "$2" --agree-tos

# fix rights
chown -R root:nginx /etc/letsencrypt
chmod -R 740 /etc/letsencrypt
find /etc/letsencrypt -type d -exec chmod 750 {} \;
