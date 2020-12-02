#!/bin/sh

# replace pattern in file
function replace_in_file() {
        # escape slashes
        pattern=$(echo "$2" | sed "s/\//\\\\\//g")
        replace=$(echo "$3" | sed "s/\//\\\\\//g")
        replace=$(echo "$replace" | sed "s/\\ /\\\\ /g")
        sed -i "s/$pattern/$replace/g" "$1"
}

BLACKLIST="$(curl -s https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list)"
DATA=""
IFS=$'\n'
for ref in $BLACKLIST ; do
        DATA="${DATA}\"~${ref}\" yes;\n"
done

cp /opt/confs/global/map-referrer.conf /etc/nginx/map-referrer.conf
replace_in_file "/etc/nginx/map-referrer.conf" "%BLOCK_REFERRER%" "$DATA"
cp /etc/nginx/map-referrer.conf /cache

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
