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
	fi
}
trap "trap_exit" TERM INT QUIT

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

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing autoconf ..."
/usr/share/bunkerweb/autoconf/main.py &
pid="$!"

wait "$pid"
exit_code=$?

if [ -f /var/tmp/bunkerweb/autoconf.healthy ] ; then
	rm -f /var/tmp/bunkerweb/autoconf.healthy
fi

log "ENTRYPOINT" "ℹ️ " "Autoconf stopped"
exit $exit_code
