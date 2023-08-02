#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/var/run/bunkerweb/scheduler.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
		kill -s TERM "$(cat /var/run/bunkerweb/scheduler.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/scheduler.pid ] ; then
	rm -f /var/run/bunkerweb/scheduler.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the job scheduler v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
/usr/share/bunkerweb/scheduler/main.py &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/scheduler.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/scheduler.healthy ] ; then
	rm /var/tmp/bunkerweb/scheduler.healthy
fi
log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit 0