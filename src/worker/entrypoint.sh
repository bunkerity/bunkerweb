#!/bin/bash

set -e

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

log "ENTRYPOINT" "ℹ️" "Starting the worker v$(cat /usr/share/bunkerweb/VERSION) ..."

/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
else
	echo "Docker" > /usr/share/bunkerweb/INTEGRATION
fi

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bw-worker}"

for i in $(seq 1 30); do
	if python3 -c "from Database import Database; from logger import setup_logger; db = Database(setup_logger('WORKER')); db.close()" >/dev/null 2>&1; then
		break
	fi

	log "ENTRYPOINT" "ℹ️" "Waiting for database (attempt $i/30) ..."
	sleep 2
done

exec celery -A worker.app worker \
	--loglevel="$(/usr/share/bunkerweb/worker/celery-loglevel.sh "${LOG_LEVEL:-info}")" \
	--concurrency="${WORKER_CONCURRENCY:-2}" \
	--pool=prefork \
	--max-tasks-per-child=1 \
	--max-memory-per-child="${WORKER_MAX_MEMORY_KB:-300000}" \
	--hostname="${WORKER_HOSTNAME:-worker@%h}" \
	--without-heartbeat \
	--without-mingle \
	--without-gossip \
	-Ofair \
	-Q "${WORKER_QUEUES:-default,heavy}"
