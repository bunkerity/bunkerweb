#!/bin/sh

# load some functions
. /opt/scripts/utils.sh

# save old conf
cp /etc/nginx/map-user-agent.conf /cache

# generate new conf
BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list)
$(curl -s https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt)"
if [ "$?" -ne 0 ] ; then
	job_log "[BLACKLIST] can't update user-agent list"
fi
DATA=""
IFS=$'\n'
for ua in $BLACKLIST ; do
        DATA="${DATA}~*${ua} yes;\n"
done
DATA_ESCAPED=$(echo "$DATA" | sed 's: :\\\\ :g' | sed 's:\\\\ yes;: yes;:g' | sed 's:\\\\\\ :\\\\ :g')
echo -e "map \$http_user_agent \$bad_user_agent { default no; $DATA_ESCAPED }" > /tmp/map-user-agent.conf

# check number of lines
lines="$(wc -l /etc/nginx/map-user-agent.conf | cut -d ' ' -f 1)"
if [ "$lines" -gt 1 ] ; then
	mv /tmp/map-user-agent.conf /etc/nginx/map-user-agent.conf
	job_log "[BLACKLIST] user-agent list updated ($lines entries)"
	if [ -f /tmp/nginx.pid ] ; then
		/usr/sbin/nginx -s reload > /dev/null 2>&1
		if [ "$?" -eq 0 ] ; then
			cp /etc/nginx/map-user-agent.conf /cache
			job_log "[NGINX] successfull nginx reload after user-agent list update"
		else
			cp /cache/map-user-agent.conf /etc/nginx
			job_log "[NGINX] failed nginx reload after user-agent list update fallback to old list"
			/usr/sbin/nginx -s reload > /dev/null 2>&1
		fi
	else
		cp /etc/nginx/map-user-agent.conf /cache
	fi
else
	job_log "[BLACKLIST] can't update user-agent list"

fi

rm -f /tmp/map-user-agent.conf 2> /dev/null
