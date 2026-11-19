#!/bin/bash

# Load utility functions from a shared helper script.
# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# Define a function to handle SIGTERM and SIGINT signals.
# shellcheck disable=SC2329
function trap_exit() {
	# Log that the script caught a termination signal.
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"

	# Stop the API process if it exists.
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/api.pid" ]; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Stopping API ..."

		# Verify the API process is running before stopping it.
		# shellcheck disable=SC2317
		if kill -0 "$(cat /var/run/bunkerweb/api.pid)" 2> /dev/null; then
			# Send a TERM signal to stop the API.
			# shellcheck disable=SC2317
			kill -s TERM "$(cat /var/run/bunkerweb/api.pid)"
		fi

		# Log that the API process has been stopped.
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "API stopped"
	# The child may not have written its PID file yet: signal it directly.
	elif [ -n "${pid:-}" ]; then
		# shellcheck disable=SC2317
		kill -s TERM "$pid" 2> /dev/null
	fi
}

# Register the trap_exit function to handle SIGTERM, SIGINT, and SIGQUIT signals.
trap 'wait_interrupted=yes; stop_requested=yes; trap_exit' TERM INT QUIT

# Remove any existing PID file for the API to avoid stale state issues.
if [ -f /var/run/bunkerweb/api.pid ]; then
	rm -f /var/run/bunkerweb/api.pid
fi

# Log the startup of the API, including the version being launched.
log "ENTRYPOINT" "ℹ️" "Starting the API v$(cat /usr/share/bunkerweb/VERSION) ..."

# Set up and validate the /data folder, ensuring required configurations are present.
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

# Determine the deployment mode (Swarm, Kubernetes, Autoconf, or Docker) and record it.
if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]]; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]]; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]]; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
else
	echo "Docker" > /usr/share/bunkerweb/INTEGRATION
fi

if [ ! -f /etc/bunkerweb/api.yml ]; then
	touch /etc/bunkerweb/api.yml
fi

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bw-api}"

# Start the main Gunicorn process with the standard logger configuration.
# A stop received before the child exists: do not start it.
if [ "${stop_requested:-no}" = yes ]; then
	log "ENTRYPOINT" "ℹ️" "Stopped before the API started"
	exit 143
fi
python3 -m gunicorn --logger-class utils.logger.APILogger --config utils/gunicorn.conf.py &
pid="$!"
# A stop received while the child was being started.
if [ "${stop_requested:-no}" = yes ]; then
	kill -s TERM "$pid" 2> /dev/null
fi

# Wait for the main API process to exit and capture its exit code.
# A stop trap interrupts wait before the child has finished shutting down.
while :; do
	wait_interrupted=no
	wait "$pid"
	exit_code=$?
	[ "$wait_interrupted" = yes ] || break
done

# Log the exit status of the main API process for debugging purposes.
log "ENTRYPOINT" "ℹ️" "API stopped with exit code $exit_code"

# Exit the script with the same exit code as the main API process.
exit "$exit_code"
