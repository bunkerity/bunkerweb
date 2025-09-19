#!/bin/bash

# Enforce a restrictive default umask for all operations
umask 027

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

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

# Function to install or upgrade a CrowdSec collection
function install_or_upgrade_collection() {
	local collection_name="$1"
	# shellcheck disable=SC2317
	if cscli collections list -o raw | grep -qw "$collection_name"; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Upgrading collection: $collection_name"
		# shellcheck disable=SC2317
		if cscli collections upgrade "$collection_name"; then
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "[CROWDSEC] Upgraded collection: $collection_name"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to upgrade collection: $collection_name"
		fi
	else
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Installing collection: $collection_name"
		# shellcheck disable=SC2317
		if cscli collections install "$collection_name"; then
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "[CROWDSEC] Installed collection: $collection_name"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to install collection: $collection_name"
		fi
	fi
}

# Function to uninstall a CrowdSec collection
function uninstall_collection() {
	local collection_name="$1"
	# shellcheck disable=SC2317
	if cscli collections list -o raw | grep -qw "$collection_name"; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Uninstalling collection: $collection_name"
		# shellcheck disable=SC2317
		if cscli collections remove "$collection_name"; then
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "[CROWDSEC] Uninstalled collection: $collection_name"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to uninstall collection: $collection_name"
		fi
	else
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Collection $collection_name is not installed, skipping uninstall."
	fi
}

# Function to install or upgrade a CrowdSec parser
function install_or_upgrade_parser() {
	local parser_name="$1"
	# shellcheck disable=SC2317
	if cscli parsers list -o raw | grep -qw "$parser_name"; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Upgrading parser: $parser_name"
		# shellcheck disable=SC2317
		if cscli parsers upgrade "$parser_name"; then
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "[CROWDSEC] Upgraded parser: $parser_name"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to upgrade parser: $parser_name"
		fi
	else
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Installing parser: $parser_name"
		# shellcheck disable=SC2317
		if cscli parsers install "$parser_name"; then
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "✅" "[CROWDSEC] Installed parser: $parser_name"
		else
			# shellcheck disable=SC2317
			log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to install parser: $parser_name"
		fi
	fi
}

export MULTISITE="${MULTISITE:-yes}"

# Configure autorestart for enabled services
log "ENTRYPOINT" "ℹ️" "Configuring autostart/autorestart for enabled services..."

# Enable autorestart for UI service if enabled
if [ "${SERVICE_UI}" = "yes" ]; then
	export SERVER_NAME="${SERVER_NAME:-}"
	export UI_HOST="${UI_HOST:-http://127.0.0.1:7000}"
	sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/ui.ini
	log "ENTRYPOINT" "✅" "Enabled autorestart for UI service"
else
	sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/ui.ini
	log "ENTRYPOINT" "ℹ️" "UI service is disabled, autostart not enabled"
fi

# Enable autorestart for API service if enabled
if [ "${SERVICE_API}" = "yes" ]; then
    export API_LISTEN_ADDR="${API_LISTEN_ADDR:-${LISTEN_ADDR:-0.0.0.0}}"
    export API_LISTEN_PORT="${API_LISTEN_PORT:-${LISTEN_PORT:-8888}}"
    sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/api.ini
    log "ENTRYPOINT" "✅" "Enabled autorestart for API service"
else
    sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/api.ini
    log "ENTRYPOINT" "ℹ️" "API service is disabled, autostart not enabled"
fi

# Enable autorestart for scheduler service if enabled
if [ "${SERVICE_SCHEDULER}" = "yes" ]; then
	sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/scheduler.ini
	log "ENTRYPOINT" "✅" "Enabled autorestart for scheduler service"
else
	sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/scheduler.ini
	log "ENTRYPOINT" "ℹ️" "Scheduler service is disabled, autostart not enabled"
fi

# Enable autorestart for autoconf service if enabled
if [ "${AUTOCONF_MODE}" = "yes" ]; then
	sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/autoconf.ini
	log "ENTRYPOINT" "✅" "Enabled autorestart for autoconf service"
else
	sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/autoconf.ini
	log "ENTRYPOINT" "ℹ️" "Autoconf service is disabled, autostart not enabled"
fi

if [ "${USE_CROWDSEC}" = "yes" ] && [[ "${CROWDSEC_API:-http://127.0.0.1:8000}" == http://127.0.0.1* || "${CROWDSEC_API:-http://127.0.0.1:8000}" == http://localhost* ]]; then
	if [ -z "${CROWDSEC_APPSEC_URL+x}" ]; then
		export CROWDSEC_APPSEC_URL="http://127.0.0.1:7422"
	fi
	log "ENTRYPOINT" "ℹ️" "[CROWDSEC] The CrowdSec service is enabled. Starting configuration..."

	# Enable autorestart for CrowdSec service
	sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/crowdsec.ini
	log "ENTRYPOINT" "✅" "Enabled autorestart for CrowdSec service"

	cscli hub update
	log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Updated CrowdSec hub."

	if [ ! -s /var/lib/crowdsec/online_api_credentials.yaml ]; then
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] No Central API credentials found. Registering machine..."
		cscli capi register
		log "ENTRYPOINT" "✅" "[CROWDSEC] Machine registered successfully."
	fi

	if [ ! -f /var/lib/crowdsec/local_api_credentials.yaml ] || ! grep -q "login" /var/lib/crowdsec/local_api_credentials.yaml; then
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] No local API credentials found. Generating new ones..."
		cscli machines add -a --force
		log "ENTRYPOINT" "✅" "[CROWDSEC] Local API credentials generated."
	fi

	log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Processing required collections and parsers..."
	install_or_upgrade_collection "crowdsecurity/nginx"
	install_or_upgrade_collection "crowdsecurity/linux"

	if [[ "${CROWDSEC_APPSEC_URL}" == http://127.0.0.1* || "${CROWDSEC_APPSEC_URL}" == http://localhost* ]]; then
		install_or_upgrade_collection "crowdsecurity/appsec-virtual-patching"
		install_or_upgrade_collection "crowdsecurity/appsec-generic-rules"
	else
		uninstall_collection "crowdsecurity/appsec-virtual-patching"
		uninstall_collection "crowdsecurity/appsec-generic-rules"
	fi

	install_or_upgrade_parser "crowdsecurity/geoip-enrich"
	install_or_upgrade_parser "crowdsecurity/docker-logs"
	install_or_upgrade_parser "crowdsecurity/cri-logs"
	log "ENTRYPOINT" "✅" "[CROWDSEC] Required parsers and collections processed."

	# Optionally disable specific parsers provided by user
	if [ -n "${CROWDSEC_DISABLE_PARSERS}" ]; then
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Disabling parsers: ${CROWDSEC_DISABLE_PARSERS}"
		IFS=' ' read -ra PARSERS <<< "${CROWDSEC_DISABLE_PARSERS}"
		for parser in "${PARSERS[@]}"; do
			if cscli parsers remove "$parser" --force; then
				log "ENTRYPOINT" "✅" "[CROWDSEC] Disabled parser: $parser"
			else
				log "ENTRYPOINT" "❌" "[CROWDSEC] Failed to disable parser: $parser"
			fi
		done
	fi

	if [ -n "${CROWDSEC_EXTRA_COLLECTIONS}" ]; then
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Processing extra collections: ${CROWDSEC_EXTRA_COLLECTIONS}"
		IFS=' ' read -ra COLLECTIONS <<< "${CROWDSEC_EXTRA_COLLECTIONS}"
		for collection in "${COLLECTIONS[@]}"; do
			install_or_upgrade_collection "$collection"
		done
		log "ENTRYPOINT" "✅" "[CROWDSEC] Extra collections processed."
	fi

	log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Configuring bouncer..."

	BOUNCER_KEY=""
	[ -f /var/lib/crowdsec/bunkerweb.key ] && BOUNCER_KEY=$(cat /var/lib/crowdsec/bunkerweb.key)

	if cscli bouncers inspect crowdsec-bunkerweb-bouncer/v1.6 >/dev/null 2>&1; then
		BOUNCER_EXISTS=true
	else
		BOUNCER_EXISTS=false
	fi

	if [ -n "${CROWDSEC_API_KEY}" ]; then
		if $BOUNCER_EXISTS && [ "$BOUNCER_KEY" != "${CROWDSEC_API_KEY}" ]; then
			log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Provided Bouncer key differs from registered one. Registering new key..."
			cscli bouncers delete crowdsec-bunkerweb-bouncer/v1.6
			BOUNCER_EXISTS=false
		fi
		if ! $BOUNCER_EXISTS; then
			cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --key "${CROWDSEC_API_KEY}"
			log "ENTRYPOINT" "✅" "[CROWDSEC] Bouncer registered with provided API key."
		fi
		BOUNCER_KEY="${CROWDSEC_API_KEY}"
	elif ! $BOUNCER_EXISTS; then
		BOUNCER_KEY=$(cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --output raw)
		log "ENTRYPOINT" "✅" "[CROWDSEC] Bouncer registered with generated API key."
	else
		log "ENTRYPOINT" "ℹ️" "[CROWDSEC] Bouncer already registered. No changes made."
	fi

	echo "$BOUNCER_KEY" > /var/lib/crowdsec/bunkerweb.key
	chmod 600 /var/lib/crowdsec/bunkerweb.key

	export CROWDSEC_API="http://127.0.0.1:8000"
	export CROWDSEC_API_KEY="${BOUNCER_KEY}"
	log "ENTRYPOINT" "✅" "[CROWDSEC] Configuration completed successfully."
else
	sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/crowdsec.ini
	log "ENTRYPOINT" "ℹ️" "CrowdSec service is disabled, autostart not enabled"
fi

if [ "${USE_REDIS}" = "yes" ] && { [ "${REDIS_HOST:-127.0.0.1}" = "127.0.0.1" ] || [ "${REDIS_HOST:-127.0.0.1}" = "localhost" ]; }; then
	mkdir -p /var/lib/redis
	export REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
	# Enable autorestart for Redis service
	sed -i 's/autorestart=false/autorestart=true/' /etc/supervisor.d/redis.ini
	log "ENTRYPOINT" "✅" "Enabled autorestart for Redis service"
else
	sed -i 's/autostart=true/autostart=false/' /etc/supervisor.d/redis.ini
	log "ENTRYPOINT" "ℹ️" "Redis service is disabled, autostart not enabled"
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
