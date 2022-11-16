#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

if [ -f /var/tmp/bunkerweb/scheduler.pid ] ; then
	rm -f /var/tmp/bunkerweb/scheduler.pid
fi

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

if [ "$SWARM_MODE" == "yes" ] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [ "$KUBERNETES_MODE" == "yes" ] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [ "$AUTOCONF_MODE" == "yes" ] ; then
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

if [ -f /var/lib/bunkerweb/db.sqlite3 ] ; then
	chown scheduler:scheduler /var/lib/bunkerweb/db.sqlite3
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
/usr/share/bunkerweb/scheduler/main.py

log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit 0