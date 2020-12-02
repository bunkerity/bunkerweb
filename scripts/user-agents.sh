#!/bin/sh

if [ ! -f "/etc/nginx/map-user-agent.conf" ] ; then
	echo "" > /etc/nginx/map-user-agent.conf
fi

BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list)"
DATA=""
IFS=$'\n'
for ua in $BLACKLIST ; do
        DATA="${DATA}~*(?:\\\\b)${ua}(?:\\\\b) yes;\n"
done
DATA_ESCAPED=$(echo "$DATA" | sed 's: :\\\\ :g' | sed 's:\\\\ yes;: yes;:g' | sed 's:\\\\\\ :\\\\ :g')

echo -e "map \$http_user_agent \$bad_user_agent { default no; $DATA_ESCAPED }" > /etc/nginx/map-user-agent.conf
cp /etc/nginx/map-user-agent.conf /cache

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
