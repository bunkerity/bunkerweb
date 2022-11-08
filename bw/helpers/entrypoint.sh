#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb v$(cat /opt/bunkerweb/VERSION) ..."

# setup and check /data folder
/opt/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️" "Catched stop operation"
	log "ENTRYPOINT" "ℹ️" "Stopping nginx ..."
	/usr/sbin/nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	log "ENTRYPOINT" "ℹ️" "Catched reload operation"
	if [ -f /opt/bunkerweb/tmp/nginx.pid ] ; then
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
	echo "Swarm" > /opt/bunkerweb/INTEGRATION
elif [ "$KUBERNETES_MODE" == "yes" ] ; then
	echo "Kubernetes" > /opt/bunkerweb/INTEGRATION
elif [ "$AUTOCONF_MODE" == "yes" ] ; then
	echo "Autoconf" > /opt/bunkerweb/INTEGRATION
fi

# start nginx
log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
nginx -g "daemon off;" &
pid="$!"

# wait while nginx is running
wait "$pid"
while [ -f "/opt/bunkerweb/tmp/nginx.pid" ] ; do
	wait "$pid"
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb stopped"
exit 0
