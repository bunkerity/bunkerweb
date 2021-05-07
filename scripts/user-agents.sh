#!/bin/sh

# load some functions
. /opt/entrypoint/utils.sh

# save old conf
cp /etc/nginx/map-user-agent.conf /cache

# generate new conf
IFS= BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list;
curl -s https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt | sort -u)"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update user-agent list"
fi
echo -e "map \$http_user_agent \$bad_user_agent { default no; $(echo $BLACKLIST | sed 's: :\\ :g;s:^:~*:;s:$: yes;:') }" > /tmp/map-user-agent.conf

# if we are running nginx
if [ -f /tmp/nginx.pid ] ; then
	RELOAD="/usr/sbin/nginx -s reload"
# if we are in autoconf
elif [ -S /tmp/autoconf.sock ] ; then
	RELOAD="/opt/entrypoint/reload.py"
fi

# check number of lines
lines="$(wc -l /tmp/map-user-agent.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	mv /tmp/map-user-agent.conf /etc/nginx/map-user-agent.conf
	job_log "[BLACKLIST] user-agent list updated ($lines entries)"
	if [ "$RELOAD" != "" ] ; then
		$RELOAD > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/map-user-agent.conf /cache
			job_log "[NGINX] successfull nginx reload after user-agent list update"
		else
			cp /cache/map-user-agent.conf /etc/nginx
			job_log "[NGINX] failed nginx reload after user-agent list update fallback to old list"
			$RELOAD > /dev/null 2>&1
		fi
	else
		cp /etc/nginx/map-user-agent.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update user-agent list"
fi

rm -f /tmp/map-user-agent.conf 2> /dev/null
