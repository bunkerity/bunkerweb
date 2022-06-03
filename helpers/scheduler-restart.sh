#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

log "SCHEDULER" "ℹ️" "Doing a restart ..."

# Kill the running scheduler
retry=0
if [ -f "/opt/bunkerweb/tmp/scheduler.pid" ] ; then
	kill -s TERM "$(cat /opt/bunkerweb/tmp/scheduler.pid)"
	ret=$?
	if [ $? -ne 0 ] ; then
		log "SCHEDULER" "❌" "Error while sending signal to running scheduler (exit status = $ret)"
		exit 1
	fi
	while [ -f "/opt/bunkerweb/tmp/scheduler.pid" ] && [ $retry -lt 3 ] ; do
		echo log "SCHEDULER" "ℹ️" "Waiting for scheduler to stop ..."
		sleep 5
		retry=$((retry + 1))
	done
	if [ $retry -eq 3 ] ; then
		log "SCHEDULER" "❌" "Timeout while waiting while waiting for scheduler to stop"
		exit 1
	fi
fi

# Run jobs once in foreground
log "SCHEDULER" "ℹ️" "Executing jobs ..."
/opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env --run
ret=$?
if [ $? -ne 0 ] ; then
	log "SCHEDULER" "❌" "Error while running jobs (exit status = $ret)"
	exit 1
fi

# Run jobs scheduler in background
/opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env &
ret=$?
if [ $? -ne 0 ] ; then
	log "SCHEDULER" "❌" "Error while running jobs (exit status = $ret)"
	exit 1
fi

exit 0