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

# TODO handle reload

if [ -f /var/run/bunkerweb/core.pid ] ; then
	rm -f /var/run/bunkerweb/core.pid
fi

log "ENTRYPOINT" "ℹ️ " "Starting the core v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

python3 /usr/share/bunkerweb/core/app/core.py > /dev/null

if [ $? == 1 ] ; then
  log "ENTRYPOINT" "❌ " "Invalid LISTEN_PORT, It must be an integer between 1 and 65535."
  exit 1
elif [ $? == 2 ] ; then
  log "ENTRYPOINT" "❌ " "Invalid MAX_WORKERS, It must be a positive integer."
  exit 1
elif [ $? == 3 ] ; then
  log "ENTRYPOINT" "❌ " "Invalid MAX_THREADS, It must be a positive integer."
  exit 1
fi

source /tmp/core.tmp.env
rm -f /tmp/core.tmp.env

if [ $AUTOCONF_MODE == "yes" ] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
elif [ $KUBERNETES_MODE == "yes" ] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [ $SWARM_MODE == "yes" ] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
fi

# Execute core
log "ENTRYPOINT" "ℹ️ " "Executing core ..."
python3 -m gunicorn --bind $LISTEN_ADDR:$LISTEN_PORT --log-level $LOG_LEVEL --workers $MAX_WORKERS --threads $MAX_THREADS --config /usr/share/bunkerweb/core/gunicorn.conf.py &
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
