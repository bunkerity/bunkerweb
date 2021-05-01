#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

# save old conf
cp /etc/nginx/map-referrer.conf /cache

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload > /dev/null 2>&1"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# generate new conf
BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list)"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update referrers list"
fi
echo -e "map \$http_referer \$bad_referrer { hostnames; default no; $(echo $DATA | sed 's/^/"~/;s/$/" yes;/') }" > /tmp/map-referrer.conf

# check number of lines
lines="$(wc -l /tmp/map-referrer.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	mv /tmp/map-referrer.conf /etc/nginx/map-referrer.conf
	job_log "[BLACKLIST] referrers list updated ($lines entries)"
	if [ "$RELOAD" != "" ] ; then
		$RELOAD
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/map-referrer.conf /cache
			job_log "[NGINX] successfull nginx reload after referrers list update"
		else
			cp /cache/map-referrer.conf /etc/nginx
			job_log "[NGINX] failed nginx reload after referrers list update fallback to old list"
			$RELOAD
		fi
	else
		cp /etc/nginx/map-referrer.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update referrers list"
fi

rm -f /tmp/map-referrer.conf 2> /dev/null
