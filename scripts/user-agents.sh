#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

if [ $(grep "^SWARM_MODE=yes$" /etc/nginx/global.env) != "" ] && [ -f /usr/sbin/nginx ] ; then
	exit 0
fi

if [ "$(has_value BLOCK_USER_AGENT yes)" = "" ] ; then
	exit 0
fi

# save old conf
cp /etc/nginx/user-agents.list /cache

# generate new conf
BLACKLIST="$( (curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list ; curl -s https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt) | sort -u | sed 's:\\ : :g;s:\\\.:%\.:g;s:\\\\:\\:g;s:\\/:/:g;s:\-:%\-:g')"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update user-agent list"
	echo -n "" > /tmp/user-agents.list
else
	echo -e "$BLACKLIST" > /tmp/user-agents.list
fi

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# check number of lines
lines="$(wc -l /tmp/user-agents.list | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	mv /tmp/user-agents.list /etc/nginx/user-agents.list
	job_log "[BLACKLIST] user-agent list updated ($lines entries)"
	if [ "$RELOAD" != "" ] ; then
		$RELOAD > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/user-agents.list /cache
			job_log "[NGINX] successfull nginx reload after user-agent list update"
		else
			cp /cache/user-agents.list /etc/nginx
			job_log "[NGINX] failed nginx reload after user-agent list update fallback to old list"
			$RELOAD > /dev/null 2>&1
		fi
	else
		cp /etc/nginx/user-agents.list /cache
	fi
else
	job_log "[BLACKLIST] can't update user-agent list"
fi

rm -f /tmp/user-agents.list 2> /dev/null
