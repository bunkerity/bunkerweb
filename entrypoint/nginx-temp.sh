#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# start nginx with temp conf for let's encrypt challenges and API
if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] || [ "$SWARM_MODE" = "yes" ] ; then
	cp /opt/confs/global/nginx-temp.conf /tmp/nginx-temp.conf
	cp /opt/confs/global/api-temp.conf /tmp/api.conf
	if [ "$SWARM_MODE" = "yes" ] ; then
		replace_in_file "/tmp/nginx-temp.conf" "%USE_API%" "include /tmp/api.conf;"
		replace_in_file "/tmp/api.conf" "%API_URI%" "$API_URI"
		list=$(spaces_to_lua "$API_WHITELIST_IP")
		replace_in_file "/tmp/api.conf" "%API_WHITELIST_IP%" "$list"
	else
		replace_in_file "/tmp/nginx-temp.conf" "%USE_API%" ""
	fi
	replace_in_file "/tmp/nginx-temp.conf" "%HTTP_PORT%" "$HTTP_PORT"
	nginx -c /tmp/nginx-temp.conf
	if [ "$?" -eq 0 ] ; then
		echo "[*] Successfully started temp nginx"
	else
		echo "[!] Can't start temp nginx"
	fi
fi
