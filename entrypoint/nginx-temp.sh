#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

# start nginx with temp conf for let's encrypt challenges and API
if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] || [ "$SWARM_MODE" = "yes" ] || [ "$AUTO_LETS_ENCRYPT" = "yes" ] || [ "$KUBERNETES_MODE" = "yes" ] ; then
	cp /opt/bunkerized-nginx/confs/global/nginx-temp.conf /tmp/nginx-temp.conf
	cp /opt/bunkerized-nginx/confs/global/api-temp.conf /tmp/api.conf
	if [ "$SWARM_MODE" = "yes" ] || [ "$KUBERNETES_MODE" = "yes" ] ; then
		replace_in_file "/tmp/nginx-temp.conf" "%USE_API%" "include /tmp/api.conf;"
		replace_in_file "/tmp/api.conf" "%API_URI%" "$API_URI"
		API_WHITELIST_IP="${API_WHITELIST_IP-192.168.0.0/16 172.16.0.0/12 10.0.0.0/8}"
		list=$(spaces_to_lua "$API_WHITELIST_IP")
		replace_in_file "/tmp/api.conf" "%API_WHITELIST_IP%" "$list"
	else
		replace_in_file "/tmp/nginx-temp.conf" "%USE_API%" ""
	fi
	HTTP_PORT="${HTTP_PORT-8080}"
	replace_in_file "/tmp/nginx-temp.conf" "%HTTP_PORT%" "$HTTP_PORT"
	if [ "$SWARM_MODE" = "yes" ] || [ "$KUBERNETES_MODE" = "yes" ] ; then
		log "nginx-temp" "INFO" "start temporary nginx server and wait for autoconf events..."
		nginx -c /tmp/nginx-temp.conf -g 'daemon off;'
	else
		nginx -c /tmp/nginx-temp.conf -g 'daemon on;'
		if [ "$?" -eq 0 ] ; then
			log "nginx-temp" "INFO" "successfully started temp nginx"
		else
			log "nginx-temp" "ERROR" "can't start temp nginx"
		fi
	fi
fi
