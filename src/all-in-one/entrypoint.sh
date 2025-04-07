#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

# trap SIGTERM and SIGINT
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught stop operation, stopping services..."
	# Use -s to send signal to all processes in supervisord
	# shellcheck disable=SC2317
	supervisorctl shutdown

	# Wait for services to stop gracefully
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Waiting for services to stop..."

	# Wait for supervisord to exit (up to 30 seconds)
	# shellcheck disable=SC2317
	local timeout=30
	# shellcheck disable=SC2317
	local counter=0
	# shellcheck disable=SC2317
	while pgrep -f "supervisord" > /dev/null && [ "$counter" -lt "$timeout" ]; do
		# shellcheck disable=SC2317
		sleep 1
		# shellcheck disable=SC2317
		counter=$((counter+1))
	done

	# Check if we had to timeout
	# shellcheck disable=SC2317
	if pgrep -f "supervisord" > /dev/null; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "⚠️" "Services didn't stop within $timeout seconds, forcing shutdown..."
		# shellcheck disable=SC2317
		pkill -15 -f "supervisord"
	else
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "✅" "All services stopped successfully"
	fi
}
trap trap_exit TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught reload operation"

	# Check if supervisord is running before attempting reload
	# shellcheck disable=SC2317
	if pgrep -f "supervisord" > /dev/null; then
		# Reload supervisord configuration
		# shellcheck disable=SC2317
		if supervisorctl update all; then
			# Restart all services to apply changes
			# shellcheck disable=SC2317
			supervisorctl restart all
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "Reload successful"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "Failed to update supervisord configuration"
		fi
	else
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "❌" "Supervisord is not running"
	fi
}
trap trap_reload HUP

export MULTISITE="${MULTISITE:-yes}"
if [ "${SERVICE_UI}" = "yes" ]; then
	export SERVER_NAME="${SERVER_NAME:-}"
	export UI_HOST="${UI_HOST:-http://127.0.0.1:7000}"
fi

# start supervisord in foreground
log "ENTRYPOINT" "ℹ️" "Starting services ..."
/usr/bin/supervisord -c /etc/supervisord.conf &
pid="$!"

# wait while supervisor is running
wait "$pid"
while [ -f "/var/run/bunkerweb/supervisord.pid" ] ; do
	wait "$pid"
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb AIO stopped"
exit 0
