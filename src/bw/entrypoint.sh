#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

shopt -s nullglob
ascii_array=(/usr/share/bunkerweb/misc/*.ascii)
shopt -u nullglob
cat "${ascii_array[$((RANDOM % ${#ascii_array[@]}))]}"

log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught stop operation, stopping nginx ..."
	# shellcheck disable=SC2317
	nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught reload operation"
	# shellcheck disable=SC2317
	if [ -f /var/run/bunkerweb/nginx.pid ] ; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "Reloading nginx ..."
		nginx -s reload
		# shellcheck disable=SC2181,SC2317
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

# generate "temp" config
echo -e "IS_LOADING=yes\nUSE_BUNKERNET=no\nSEND_ANONYMOUS_REPORT=no\nSERVER_NAME=\nMODSECURITY_CRS_VERSION=${MODSECURITY_CRS_VERSION:-4}\nAPI_HTTP_PORT=${API_HTTP_PORT:-5000}\nAPI_SERVER_NAME=${API_SERVER_NAME:-bwapi}\nAPI_WHITELIST_IP=${API_WHITELIST_IP:-127.0.0.0/8}\nUSE_REAL_IP=${USE_REAL_IP:-no}\nUSE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL:-no}\nREAL_IP_FROM=${REAL_IP_FROM:-192.168.0.0/16 172.16.0.0/12 10.0.0.0/8}\nREAL_IP_HEADER=${REAL_IP_HEADER:-X-Forwarded-For}\nHTTP_PORT=${HTTP_PORT:-8080}\nHTTPS_PORT=${HTTPS_PORT:-8443}" > /tmp/variables.env
python3 /usr/share/bunkerweb/gen/main.py --variables /tmp/variables.env

# start nginx
log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
nginx -g "daemon off;" &
pid="$!"

# wait while nginx is running
wait "$pid"
while [ -f "/var/run/bunkerweb/nginx.pid" ] ; do
	wait "$pid"
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb stopped"
exit 0
