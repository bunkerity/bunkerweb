#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/var/run/bunkerweb/core.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping core ..."
		kill -s TERM "$(cat /var/run/bunkerweb/core.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/core.pid ] ; then
	rm -f /var/run/bunkerweb/core.pid
fi

log "ENTRYPOINT" "ℹ️ " "Starting the core v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

python3 /usr/share/bunkerweb/core/app/core.py > /dev/null

if [ $? -ne 0 ] ; then
  log "ENTRYPOINT" "❌ " "Invalid LISTEN_PORT, It must be an integer between 1 and 65535."
  exit 1
fi

read LISTEN_ADDR LISTEN_PORT LOG_LEVEL AUTOCONF_MODE KUBERNETES_MODE SWARM_MODE < <(echo $(python3 /usr/share/bunkerweb/core/app/core.py | jq -r '.listen_addr, .listen_port, .log_level, .autoconf_mode, .kubernetes_mode, .swarm_mode'))

if $AUTOCONF_MODE ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
elif $KUBERNETES_MODE ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif $SWARM_MODE ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
fi

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing core ..."
python3 -m gunicorn --bind $LISTEN_ADDR:$LISTEN_PORT --log-level $LOG_LEVEL --config /usr/share/bunkerweb/core/gunicorn.conf.py &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/core.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/core.healthy ] ; then
	rm /var/tmp/bunkerweb/core.healthy
fi
log "ENTRYPOINT" "ℹ️ " "Core stopped"
exit 0
