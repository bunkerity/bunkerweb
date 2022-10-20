#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

if [ -f /opt/bunkerweb/tmp/scheduler.pid ] ; then
	rm -f /opt/bunkerweb/tmp/scheduler.pid
fi

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
else
	VARIABLES_PATH="/etc/nginx/variables.env"
fi

# Init database
get_env > "/tmp/variables.env"
/opt/bunkerweb/gen/main.py --variables /tmp/variables.env --method scheduler --init
if [ "$?" -ne 0 ] ; then
	log "ENTRYPOINT" "❌" "Scheduler generator failed"
	exit 1
fi

if [ -v VARIABLES_PATH ] && [ -f "/etc/nginx/variables.env" ] && grep -q "^TEMP_NGINX=no$" /etc/nginx/variables.env ; then
	log "ENTRYPOINT" "⚠️ " "Looks like BunkerWeb configuration is already generated, will not generate it again"
elif [ "$SWARM_MODE" != "yes" ] && [ "$KUBERNETES_MODE" != "yes" ] && [ "$AUTOCONF_MODE" != "yes" ] ; then
	# Generate configuration and send config to bunkerweb
	/opt/bunkerweb/gen/main.py --method scheduler
	if [ "$?" -ne 0 ] ; then
		log "ENTRYPOINT" "❌" "Scheduler generator failed"
		exit 1
	fi
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing jobs ..."
if [ -v VARIABLES_PATH ] ; then
	/opt/bunkerweb/scheduler/main.py --variables $VARIABLES_PATH --run
else
	/opt/bunkerweb/scheduler/main.py --run
fi
if [ "$?" -ne 0 ] ; then
  log "ENTRYPOINT" "❌" "Scheduler failed"
  exit 1
fi


log "ENTRYPOINT" "ℹ️ " "Executing job scheduler ..."
if [ -v VARIABLES_PATH ] ; then
	/opt/bunkerweb/scheduler/main.py --variables $VARIABLES_PATH
else
	/opt/bunkerweb/scheduler/main.py
fi

log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit 0