#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/var/tmp/bunkerweb/scheduler.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
		kill -s TERM "$(cat /var/tmp/bunkerweb/scheduler.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/tmp/bunkerweb/scheduler.pid ] ; then
	rm -f /var/tmp/bunkerweb/scheduler.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the job scheduler v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

if ! grep -q "Docker" /usr/share/bunkerweb/INTEGRATION ; then
	# Init database
	get_env > "/tmp/variables.env"
	/usr/share/bunkerweb/gen/save_config.py --variables /tmp/variables.env --init
	if [ "$?" -ne 0 ] ; then
		log "ENTRYPOINT" "❌" "Scheduler generator failed"
		exit 1
	fi
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
/usr/share/bunkerweb/scheduler/main.py &
pid="$!"
wait "$pid"
while [ -f /var/tmp/bunkerweb/scheduler.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/scheduler.healthy ] ; then
	rm /var/tmp/bunkerweb/scheduler.healthy
fi
log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit 0