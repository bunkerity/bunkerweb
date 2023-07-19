#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/var/run/bunkerweb/api.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping api ..."
		kill -s TERM "$(cat /var/run/bunkerweb/api.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/api.pid ] ; then
	rm -f /var/run/bunkerweb/api.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the api v$(cat /usr/share/bunkerweb/VERSION) ..."

DEFAULT_LOG_LEVEL="INFO"
DEFAULT_SWARM_MODE="no"
DEFAULT_KUBERNETES_MODE="no"
DEFAULT_AUTOCONF_MODE="no"
DEFAULT_LISTEN_ADDR="0.0.0.0"
DEFAULT_LISTEN_PORT="1337"
DEFAULT_API_WHITELIST="127.0.0.1"
DEFAULT_API_CHECK_WHITELIST="yes"

for variable in "LOG_LEVEL" "SWARM_MODE" "KUBERNETES_MODE" "AUTOCONF_MODE" "LISTEN_ADDR" "LISTEN_PORT" "API_WHITELIST" "API_CHECK_WHITELIST" ; do
	if [ -z "${!variable}" ] ; then
		if grep -Pq "^$variable" /etc/bunkerweb/api.conf
		then
				export "$variable"="$(grep "$variable" /etc/bunkerweb/api.conf | cut -d "=" -f2)"
		else
				export "$variable"="$(eval echo "\$DEFAULT_$variable")"
		fi
	fi
done

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing api ..."
python3 -m gunicorn --bind $LISTEN_ADDR:$LISTEN_PORT --log-level $LOG_LEVEL --config /usr/share/bunkerweb/api/gunicorn.conf.py &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/api.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/api.healthy ] ; then
	rm /var/tmp/bunkerweb/api.healthy
fi
log "ENTRYPOINT" "ℹ️ " "API stopped"
exit 0
