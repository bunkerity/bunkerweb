#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
# shellcheck disable=SC2329
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/autoconf.pid" ] ; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Stopping job autoconf ..."
		# shellcheck disable=SC2317
		kill -s TERM "$(cat /var/run/bunkerweb/autoconf.pid)"
	# The child may not have written its PID file yet: signal it directly.
	elif [ -n "${pid:-}" ] ; then
		# shellcheck disable=SC2317
		kill -s TERM "$pid" 2> /dev/null
	fi
}
trap 'wait_interrupted=yes; stop_requested=yes; trap_exit' TERM INT QUIT

if [ -f /var/run/bunkerweb/autoconf.pid ] ; then
	rm -f /var/run/bunkerweb/autoconf.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the job autoconf v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bw-autoconf}"

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing autoconf ..."
# A stop received before the child exists: do not start it.
if [ "${stop_requested:-no}" = yes ] ; then
	log "ENTRYPOINT" "ℹ️ " "Stopped before autoconf started"
	exit 143
fi
/usr/share/bunkerweb/autoconf/main.py &
pid="$!"
# A stop received while the child was being started.
if [ "${stop_requested:-no}" = yes ] ; then
	kill -s TERM "$pid" 2> /dev/null
fi

# A stop trap interrupts wait before the child has finished shutting down.
while :; do
	wait_interrupted=no
	wait "$pid"
	exit_code=$?
	[ "$wait_interrupted" = yes ] || break
done

if [ -f /var/tmp/bunkerweb/autoconf.healthy ] ; then
	rm -f /var/tmp/bunkerweb/autoconf.healthy
fi

log "ENTRYPOINT" "ℹ️ " "Autoconf stopped"
exit "$exit_code"
