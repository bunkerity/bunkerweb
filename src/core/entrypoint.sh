#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

function stop() {
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/core.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping core ..."
		kill -s TERM "$(cat /var/run/bunkerweb/core.pid)"
	fi
}

function start() {
	output="$(python3 /usr/share/bunkerweb/core/app/core.py 2>&1)"
	ret=$?

	if [ $ret == 1 ] ; then
		# Show the output of the core
		log "ENTRYPOINT" "❌ " "$output"
		exit 1
	elif [ $ret == 2 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid LISTEN_PORT, It must be an integer between 1 and 65535."
		exit 1
	elif [ $ret == 3 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid MAX_WORKERS, It must be a positive integer."
		exit 1
	elif [ $ret == 4 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid MAX_THREADS, It must be a positive integer."
		exit 1
	fi

	# shellcheck disable=SC1091
	source /tmp/core.tmp.env
	rm -f /tmp/core.tmp.env

	if [ "$AUTOCONF_MODE" == "yes" ] ; then
		echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
	elif [ "$KUBERNETES_MODE" == "yes" ] ; then
		echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
	elif [ "$SWARM_MODE" == "yes" ] ; then
		echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
	fi

	# Execute core
	log "ENTRYPOINT" "ℹ️ " "Executing core ..."
	python3 -m gunicorn --bind "$LISTEN_ADDR":"$LISTEN_PORT" --log-level "$LOG_LEVEL" --workers "$MAX_WORKERS" --threads "$MAX_THREADS" --config /usr/share/bunkerweb/core/gunicorn.conf.py &
	pid="$!"
	wait "$pid"
	while [ -f /var/run/bunkerweb/core.pid ] ; do
			wait "$pid"
	done
}

# trap SIGTERM and SIGINT
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
	# shellcheck disable=SC2317
	stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught reload operation"
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/core.pid" ] ; then
		stop
		start
	fi
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Reloaded"
}
trap "trap_reload" HUP

if [ -f /var/run/bunkerweb/core.pid ] ; then
	rm -f /var/run/bunkerweb/core.pid
fi

log "ENTRYPOINT" "ℹ️ " "Starting the core v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

start

if [ -f /var/tmp/bunkerweb/core.healthy ] ; then
	rm /var/tmp/bunkerweb/core.healthy
fi
log "ENTRYPOINT" "ℹ️ " "Core stopped"
exit 0
