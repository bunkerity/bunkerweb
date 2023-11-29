#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

function stop() {
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/core.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping core ..."
		kill -s TERM "$(cat /var/run/bunkerweb/core.pid)"

		count=0
    while [ -f "/var/run/bunkerweb/core.pid" ] ; do
        sleep 1
        count=$((count + 1))
        if [ "$count" -ge 10 ] ; then
            break
        fi
    done

    if [ "$count" -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting core to stop"
        exit 1
    fi

		log "ENTRYPOINT" "ℹ️ " "Core stopped"
	fi
}

function start() {
	python3 /usr/share/bunkerweb/core/app/core.py
	ret=$?

	if [ $ret -ne 0 ] ; then
		exit $ret
	fi

	set -a # turn on automatic exporting
	# shellcheck disable=SC1091
	source /tmp/core.tmp.env
	set +a # turn off automatic exporting
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
	python3 -m gunicorn --config /usr/share/bunkerweb/core/gunicorn.conf.py --bind "$LISTEN_ADDR":"$LISTEN_PORT" &
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
