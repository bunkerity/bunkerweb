#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# start nginx with temp conf for let's encrypt challenges
if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] ; then
	cp /opt/confs/global/nginx-temp.conf /tmp/nginx-temp.conf
	replace_in_file "/tmp/nginx-temp.conf" "%HTTP_PORT%" "$HTTP_PORT"
	nginx -c /tmp/nginx-temp.conf
	if [ "$?" -eq 0 ] ; then
		echo "[*] Successfully started temp nginx to solve Let's Encrypt challenges"
	else
		echo "[!] Can't start temp nginx to solve Let's Encrypt challenges"
	fi
fi
