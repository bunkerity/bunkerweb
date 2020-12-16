#!/bin/sh

. /opt/scripts/utils.sh

# MMDB from https://db-ip.com/db/download/ip-to-country-lite
URL="https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz"
wget -O /cache/geoip.mmdb.gz "$URL" > /dev/null 2>&1
if [ -f /cache/geoip.mmdb.gz ] ; then
	gunzip -f /cache/geoip.mmdb.gz > /dev/null 2>&1
	if [ "$?" -ne 0 ] ; then
		job_log "[GEOIP] can't extract DB from $URL"
		exit 1
	fi
	cp /cache/geoip.mmdb /etc/nginx/geoip.mmdb
	if [ -f /tmp/nginx.pid ] ; then
		/usr/sbin/nginx -s reload > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			job_log "[NGINX] successfull nginx reload after GeoIP DB update"
		else
			job_log "[NGINX] failed nginx reload after GeoIP DB update"
		fi
	fi
else
	job_log "[GEOIP] can't download DB from $URL"
fi
