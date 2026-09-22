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

# Keep common Celery options identical for both independently sized pools.
worker_command=(celery -A worker.app worker
	--loglevel="$(/usr/share/bunkerweb/worker/celery-loglevel.sh "${LOG_LEVEL:-info}")"
	--pool=prefork --max-tasks-per-child=1
	--without-heartbeat --without-mingle --without-gossip -Ofair)
default_command=("${worker_command[@]}"
	--concurrency="${WORKER_CONCURRENCY:-2}"
	--max-memory-per-child="${WORKER_MAX_MEMORY_KB:-300000}"
	--hostname="${WORKER_HOSTNAME:-worker@%h}"
	-Q "${WORKER_QUEUES:-default}")

# An explicitly empty heavy queue list retains the single-process escape hatch.
if [[ -z "${WORKER_HEAVY_QUEUES-heavy}" ]]; then
	exec "${default_command[@]}"
fi

# Bash stays PID 1: exec would discard the traps and orphan the other worker.
worker_pids=()
shutdown() {
	trap '' TERM INT
	kill -TERM "${worker_pids[@]}" 2>/dev/null || true
	for pid in "${worker_pids[@]}"; do
		wait "$pid" || true
	done
}
trap 'shutdown; exit 0' TERM INT

"${default_command[@]}" &
worker_pids+=("$!")
"${worker_command[@]}" \
	--concurrency="${WORKER_HEAVY_CONCURRENCY:-1}" \
	--max-memory-per-child="${WORKER_HEAVY_MAX_MEMORY_KB:-${WORKER_MAX_MEMORY_KB:-300000}}" \
	--hostname="${WORKER_HEAVY_HOSTNAME:-worker-heavy@%h}" \
	-Q "${WORKER_HEAVY_QUEUES-heavy}" &
worker_pids+=("$!")

# Any unsolicited master exit, even status 0, makes the container unhealthy.
status=0
wait -n "${worker_pids[@]}" || status=$?
# A failed lane must not delay container recovery behind the surviving warm worker.
(
	sleep "${WORKER_FAILOVER_GRACE:-30}"
	kill -KILL "${worker_pids[@]}" 2>/dev/null || true
) &
watchdog=$!
shutdown
kill "$watchdog" 2>/dev/null || true
wait "$watchdog" 2>/dev/null || true
if [[ "$status" -eq 0 ]]; then
	status=1
fi
exit "$status"
