#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

ascii_array=($(ls /usr/share/bunkerweb/*.ascii))
cat ${ascii_array[$(($RANDOM % ${#ascii_array[@]}))]}

log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️" "Catched stop operation"
	log "ENTRYPOINT" "ℹ️" "Stopping nginx ..."
	nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	log "ENTRYPOINT" "ℹ️" "Catched reload operation"
	if [ -f /var/tmp/bunkerweb/nginx.pid ] ; then
		log "ENTRYPOINT" "ℹ️" "Reloading nginx ..."
		nginx -s reload
		if [ $? -eq 0 ] ; then
			log "ENTRYPOINT" "ℹ️" "Reload successful"
		else
			log "ENTRYPOINT" "❌" "Reload failed"
		fi
	else
		log "ENTRYPOINT" "⚠️" "Ignored reload operation because nginx is not running"
	fi
}
trap "trap_reload" HUP

if [ "$SWARM_MODE" == "yes" ] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [ "$KUBERNETES_MODE" == "yes" ] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [ "$AUTOCONF_MODE" == "yes" ] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

if [ -f "/etc/nginx/variables.env" ] ; then
	log "ENTRYPOINT" "⚠️ " "Looks like BunkerWeb has already been loaded, will not generate temp config"
else
	# generate "temp" config
	echo -e "IS_LOADING=yes\nSERVER_NAME=\nAPI_HTTP_PORT=${API_HTTP_PORT:-5000}\nAPI_SERVER_NAME=${API_SERVER_NAME:-bwapi}\nAPI_WHITELIST_IP=${API_WHITELIST_IP:-127.0.0.0/8}\nUSE_REAL_IP=${USE_REAL_IP:-no}\nUSE_REAL_IP=${USE_REAL_IP:-no}\nUSE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL:-no}\nREAL_IP_FROM=${REAL_IP_FROM:-192.168.0.0/16 172.16.0.0/12 10.0.0.0/8}\nREAL_IP_HEADER=${REAL_IP_HEADER:-X-Forwarded-For}" > /tmp/variables.env
	python3 /usr/share/bunkerweb/gen/main.py --variables /tmp/variables.env
fi

# start nginx
log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
nginx -g "daemon off;" &
pid="$!"

# wait while nginx is running
wait "$pid"
while [ -f "/var/tmp/bunkerweb/nginx.pid" ] ; do
	wait "$pid"
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb stopped"
exit 0