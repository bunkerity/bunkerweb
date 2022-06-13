#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb v$(cat /opt/bunkerweb/VERSION) ..."

# setup and check /data folder
/opt/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️" "Catched stop operation"
	if [ -f "/opt/bunkerweb/tmp/scheduler.pid" ] ; then
		log "ENTRYPOINT" "ℹ️" "Stopping job scheduler ..."
		kill -s TERM "$(cat /opt/bunkerweb/tmp/scheduler.pid)"
	fi
	log "ENTRYPOINT" "ℹ️" "Stopping nginx ..."
	/usr/sbin/nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	log "ENTRYPOINT" "ℹ️" "Catched reload operation"
	/opt/bunkerweb/helpers/scheduler-restart.sh
	if [ $? -ne 0 ] ; then
		log "ENTRYPOINT" "ℹ️" "Error while restarting scheduler"
	fi
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

if [ -f /opt/bunkerweb/tmp/scheduler.pid ] ; then
	rm -f /opt/bunkerweb/tmp/scheduler.pid
fi

if [ "$SWARM_MODE" != "yes" ] && [ "$KUBERNETES_MODE" != "yes" ] && [ "$AUTOCONF_MODE" != "yes" ] ; then
	# execute temp nginx with no server
	export TEMP_NGINX="yes"
	log "ENTRYPOINT" "ℹ️" "Generating configuration for temp nginx ..."
	env | grep -E -v "^(HOSTNAME|PWD|PKG_RELEASE|NJS_VERSION|SHLVL|PATH|_|NGINX_VERSION|HOME)=" > "/tmp/variables.env"
	/opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env
	if [ "$?" -ne 0 ] ; then
		log "ENTRYPOINT" "❌" "Generator failed"
		exit 1
	fi
	log "ENTRYPOINT" "ℹ️" "Generator is successful"
	log "ENTRYPOINT" "ℹ️" "Starting temp nginx ..."
	nginx
	if [ $? -ne 0 ] ; then
		log "ENTRYPOINT" "❌" "Temp nginx failed to start"
		exit 1
	fi
	log "ENTRYPOINT" "ℹ️" "Temp nginx started"

	# execute jobs
	log "ENTRYPOINT" "ℹ️" "Executing jobs ..."
	/opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env --run

	# stop temporary nginx
	nginx -s quit
	while [ -f /opt/bunkerweb/tmp/nginx-temp.pid ] ; do
		sleep 1
	done
fi

# generate final configuration
export TEMP_NGINX="no"
log "ENTRYPOINT" "ℹ️" "Generating configuration ..."
env | grep -E -v "^(HOSTNAME|PWD|PKG_RELEASE|NJS_VERSION|SHLVL|PATH|_|NGINX_VERSION|HOME)=" > "/tmp/variables.env"
/opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env
if [ "$?" -ne 0 ] ; then
	log "ENTRYPOINT" "❌" "Generator failed"
	exit 1
fi
log "ENTRYPOINT" "ℹ️" "Generator is successful"

# execute job scheduler
if [ "$SWARM_MODE" != "yes" ] && [ "$KUBERNETES_MODE" != "yes" ] && [ "$AUTOCONF_MODE" != "yes" ] ; then
	log "ENTRYPOINT" "ℹ️" "Executing job scheduler ..."
	/opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env &
else
	log "ENTRYPOINT" "ℹ️" "Skipped execution of job scheduler because BunkerWeb is running in cluster mode"
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