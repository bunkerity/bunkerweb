#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

if [ -f /opt/bunkerweb/tmp/scheduler.pid ] ; then
	rm -f /opt/bunkerweb/tmp/scheduler.pid
fi

# setup and check /data folder
/opt/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/opt/bunkerweb/tmp/scheduler.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
		kill -s TERM "$(cat /opt/bunkerweb/tmp/scheduler.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	log "ENTRYPOINT" "ℹ️ " "Catched reload operation"
	/opt/bunkerweb/helpers/scheduler-restart.sh
	if [ $? -ne 0 ] ; then
		log "ENTRYPOINT" "ℹ️ " "Error while restarting scheduler"
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

if ! grep -q "Docker" /opt/bunkerweb/INTEGRATION ; then
	# Init database
	get_env > "/tmp/variables.env"
	/opt/bunkerweb/gen/save_config.py --variables /tmp/variables.env --init
	if [ "$?" -ne 0 ] ; then
		log "ENTRYPOINT" "❌" "Scheduler generator failed"
		exit 1
	fi
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
/opt/bunkerweb/scheduler/main.py

log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit 0