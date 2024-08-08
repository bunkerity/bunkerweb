#!/bin/bash
set -e

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/ui.pid" ] ; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Stopping web UI ..."
		# shellcheck disable=SC2317
		kill -s TERM "$(cat /var/run/bunkerweb/ui.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/ui.pid ] ; then
	rm -f /var/run/bunkerweb/ui.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the web UI v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
else
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION
fi

python3 -m gunicorn --config gunicorn.conf.py --user ui --group ui --bind 0.0.0.0:7000 &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/ui.pid ] ; do
		wait "$pid"
done

if [ -f /var/tmp/bunkerweb/ui.healthy ] ; then
	rm /var/tmp/bunkerweb/ui.healthy
fi

log "ENTRYPOINT" "ℹ️" "Web UI stopped"
exit 0
