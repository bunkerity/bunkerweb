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

	# Check if the temporary web UI process exists and stop it gracefully.
	# The PID is stored in a temporary file.
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/tmp-ui.pid" ]; then
		log "ENTRYPOINT" "ℹ️ " "Stopping temporary web UI ..."

		# Verify the process is running before attempting to stop it.
		if kill -0 "$(cat /var/run/bunkerweb/tmp-ui.pid)" 2> /dev/null; then
			# Send a TERM signal to stop the temporary web UI.
			kill -s TERM "$(cat /var/run/bunkerweb/tmp-ui.pid)"
		fi

		# Log that the temporary web UI process has been stopped.
		log "ENTRYPOINT" "ℹ️ " "Temporary web UI stopped"
	# The child may not have written its PID file yet: signal it directly.
	elif [ -n "${tmp_pid:-}" ] && kill -0 "$tmp_pid" 2> /dev/null; then
		# shellcheck disable=SC2317
		kill -s TERM "$tmp_pid"
	fi

	# Similarly, stop the main web UI process if it exists.
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/ui.pid" ]; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Stopping web UI ..."

		# Verify the main web UI process is running before stopping it.
		# shellcheck disable=SC2317
		if kill -0 "$(cat /var/run/bunkerweb/ui.pid)" 2> /dev/null; then
			# Send a TERM signal to stop the main web UI.
			# shellcheck disable=SC2317
			kill -s TERM "$(cat /var/run/bunkerweb/ui.pid)"
		fi

		# Log that the main web UI process has been stopped.
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Web UI stopped"
	# The child may not have written its PID file yet: signal it directly.
	elif [ -n "${pid:-}" ]; then
		# shellcheck disable=SC2317
		kill -s TERM "$pid" 2> /dev/null
	fi
}

# Register the trap_exit function to handle SIGTERM, SIGINT, and SIGQUIT signals.
trap 'wait_interrupted=yes; stop_requested=yes; trap_exit' TERM INT QUIT

# Remove any existing PID file for the main web UI to avoid stale state issues.
if [ -f /var/run/bunkerweb/tmp-ui.pid ]; then
	rm -f /var/run/bunkerweb/tmp-ui.pid
fi
if [ -f /var/run/bunkerweb/ui.pid ]; then
	rm -f /var/run/bunkerweb/ui.pid
fi
if [ -f /var/tmp/bunkerweb/ui.error ]; then
	rm -f /var/tmp/bunkerweb/ui.error
fi

# Log the startup of the web UI, including the version being launched.
log "ENTRYPOINT" "ℹ️" "Starting the web UI v$(cat /usr/share/bunkerweb/VERSION) ..."

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

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bw-ui}"

# Start a temporary Gunicorn process with a special logger configuration.
# Unset LOG_FILE_PATH in the tmp-ui child env so tmp-ui falls back to its own
# per-process default (tmp-ui.log) instead of sharing the main UI's log file.
# A stop received before the children exist: do not start them.
if [ "${stop_requested:-no}" = yes ]; then
	log "ENTRYPOINT" "ℹ️" "Stopped before the web UI started"
	exit 143
fi
env -u LOG_FILE_PATH python3 -m gunicorn --logger-class utils.logger.TmpUiLogger --config utils/tmp-gunicorn.conf.py &
tmp_pid="$!"
# A stop received between the two launches: wait for the temporary child, do not start the main one.
if [ "${stop_requested:-no}" = yes ]; then
	log "ENTRYPOINT" "ℹ️" "Stopped before the main web UI started"
	kill -s TERM "$tmp_pid" 2> /dev/null
	while kill -0 "$tmp_pid" 2> /dev/null; do
		wait "$tmp_pid"
	done
	exit 143
fi

# Start the main Gunicorn process with the standard logger configuration.
python3 -m gunicorn --logger-class utils.logger.UiLogger --config utils/gunicorn.conf.py &
pid="$!"
# A stop received while the children were being started.
if [ "${stop_requested:-no}" = yes ]; then
	trap_exit
fi

# Wait for the main web UI process to exit and capture its exit code.
# A stop trap interrupts wait before the child has finished shutting down.
while :; do
	wait_interrupted=no
	wait "$pid"
	exit_code=$?
	[ "$wait_interrupted" = yes ] || break
done

# Log the exit status of the main web UI process for debugging purposes.
log "ENTRYPOINT" "ℹ️" "Web UI stopped with exit code $exit_code"

# If the temporary web UI process is still running, wait for it to stop.
# It may have left no PID file yet, so also check the PID captured at launch.
if [ -f "/var/run/bunkerweb/tmp-ui.pid" ] || kill -0 "$tmp_pid" 2> /dev/null; then
	log "ENTRYPOINT" "ℹ️" "Waiting for temporary Web UI to stop ..."

	# Wait in a loop until the temporary web UI process exits, with 60 second timeout
	timeout=60
	while { [ -f "/var/run/bunkerweb/tmp-ui.pid" ] || kill -0 "$tmp_pid" 2> /dev/null; } && [ $timeout -gt 0 ]; do
		sleep 1
		((timeout--))
	done

	# The error page stays up until it is dismissed, but a stop request must not wait for that.
	while [ "${stop_requested:-no}" != yes ] && [ -f "/var/tmp/bunkerweb/ui.error" ]; do
		sleep 1
	done

	if [ $timeout -eq 0 ]; then
		log "ENTRYPOINT" "⚠️" "Timeout waiting for temporary Web UI to stop"
	else
		log "ENTRYPOINT" "ℹ️" "Temporary Web UI stopped"
	fi
fi

# Exit the script with the same exit code as the main web UI process.
exit "$exit_code"
