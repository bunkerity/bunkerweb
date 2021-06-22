#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

if [ "$(grep "^SWARM_MODE=yes$" /etc/nginx/global.env)" != "" ] && [ -f /usr/sbin/nginx ] ; then
	exit 0
fi

if [ "$(has_value BLOCK_REFERRER yes)" = "" ] ; then
	exit 0
fi

# save old conf
cp /etc/nginx/referrers.list /tmp/referrers.list.bak

# generate new conf
BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list | sed 's:\.:%\.:g;s:\-:%\-:g')"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update referrers list"
	echo -n "" > /tmp/referrers.list
else
	echo -e "$BLACKLIST" > /tmp/referrers.list
fi

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] && [ -f "/etc/nginx/autoconf" ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# check number of lines
lines="$(wc -l /tmp/referrers.list | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	cp /tmp/referrers.list /etc/nginx/referrers.list
	job_log "[BLACKLIST] referrers list updated ($lines entries)"
	if [ "$RELOAD" != "" ] ; then
		$RELOAD > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			cp /tmp/referrers.list /opt/bunkerized-nginx/cache
			job_log "[NGINX] successfull nginx reload after referrers list update"
		else
			#cp /tmp/referrers.list.bak /etc/nginx
			job_log "[NGINX] failed nginx reload after referrers list update fallback to old list"
			$RELOAD > /dev/null 2>&1
		fi
	else
		cp /tmp/referrers.list /opt/bunkerized-nginx/cache
	fi
else
	job_log "[BLACKLIST] can't update referrers list"
fi

rm -f /tmp/referrers.list 2> /dev/null
rm -f /tmp/referrers.list.bak 2> /dev/null
