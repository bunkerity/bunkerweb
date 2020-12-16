#!/bin/sh

. /opt/scripts/utils.sh

echo "map \$http_referer \$bad_referrer { hostnames; default no; }" > /etc/nginx/map-referrer.conf
echo "map \$http_referer \$bad_referrer { hostnames; default no; }" > /cache/map-referrer.conf

BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list)"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update referrers list"
fi
DATA=""
IFS=$'\n'
for ref in $BLACKLIST ; do
        DATA="${DATA}\"~${ref}\" yes;\n"
done

echo -e "map \$http_referer \$bad_referrer { hostnames; default no; $DATA }" > /cache/map-referrer.conf
cp /cache/map-referrer.conf /etc/nginx/map-referrer.conf
lines="$(wc -l /etc/nginx/map-referrer.conf | cut -d ' ' -f 1)"
job_log "[BLACKLIST] referrers list updated ($lines entries)"

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after referrers list update"
	else
		job_log "[NGINX] failed nginx reload after referrers list update"
	fi
fi
