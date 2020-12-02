#!/bin/sh

BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list)"
DATA=""
IFS=$'\n'
for ref in $BLACKLIST ; do
        DATA="${DATA}\"~${ref}\" yes;\n"
done

echo "map \$http_referer \$bad_referrer { hostnames; default no; $DATA }" > /etc/nginx/map-referrer.conf
cp /etc/nginx/map-referrer.conf /cache

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
