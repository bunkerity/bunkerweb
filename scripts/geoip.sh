#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

if [ "$(grep "^SWARM_MODE=yes$" /etc/nginx/global.env)" != "" ] && [ -f /usr/sbin/nginx ] ; then
	exit 0
fi

if [ "$(has_value BLACKLIST_COUNTRY ".\+")" = "" ] && [ "$(has_value WHITELIST_COUNTRY ".\+")" = "" ] ; then
	exit 0
fi

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] && [ -f "/etc/nginx/autoconf" ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# MMDB from https://db-ip.com/db/download/ip-to-country-lite
URL="https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz"
wget -O /tmp/geoip.mmdb.gz "$URL" > /dev/null 2>&1
if [ "$?" -eq 0 ] && [ -f /tmp/geoip.mmdb.gz ] ; then
	gunzip -f /tmp/geoip.mmdb.gz > /dev/null 2>&1
	if [ "$?" -ne 0 ] ; then
		job_log "[GEOIP] can't extract DB from $URL"
		exit 1
	fi
	mv /tmp/geoip.mmdb /etc/nginx
	if [ "$RELOAD" != "" ] ; then
		$RELOAD > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/geoip.mmdb /opt/bunkerized-nginx/cache
			job_log "[NGINX] successfull nginx reload after GeoIP DB update"
		else
			job_log "[NGINX] failed nginx reload after GeoIP DB update"
			if [ -f /opt/bunkerized-nginx/cache/geoip.mmdb ] ; then
				cp /opt/bunkerized-nginx/cache/geoip.mmdb /etc/nginx/geoip.mmdb
				$RELOAD > /dev/null 2>&1
			fi
		fi
	else
		cp /etc/nginx/geoip.mmdb /opt/bunkerized-nginx/cache
	fi
else
	job_log "[GEOIP] can't download DB from $URL"
fi

rm -f /tmp/geoip* 2> /dev/null
