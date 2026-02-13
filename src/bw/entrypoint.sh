#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

shopt -s nullglob
ascii_array=(/usr/share/bunkerweb/misc/*.ascii)
shopt -u nullglob
cat "${ascii_array[$((RANDOM % ${#ascii_array[@]}))]}"

log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bunkerweb-entrypoint}"

# trap SIGTERM and SIGINT
# shellcheck disable=SC2329
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught stop operation, stopping nginx ..."
	# shellcheck disable=SC2317
	nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
# shellcheck disable=SC2329
function trap_reload() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught reload operation"
	# shellcheck disable=SC2317
	if [ -f /var/run/bunkerweb/nginx.pid ] ; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "Reloading nginx ..."
		nginx -s reload
		# shellcheck disable=SC2181,SC2317
		if [ $? -eq 0 ] ; then
			log "ENTRYPOINT" "ℹ️" "Reload successful"
		else
			log "ENTRYPOINT" "❌" "Reload failed"
		fi
	else
		log "ENTRYPOINT" "⚠️" "Ignored reload operation because nginx is not running"
	fi
}
trap "trap_reload" HUP

function generate_tmp_env_content() {
	cat <<EOF
IS_LOADING=yes
USE_BUNKERNET=no
SEND_ANONYMOUS_REPORT=no
SERVER_NAME=
MODSECURITY_CRS_VERSION=${MODSECURITY_CRS_VERSION:-4}
API_LISTEN_HTTP=${API_LISTEN_HTTP:-yes}
API_HTTP_PORT=${API_HTTP_PORT:-5000}
API_LISTEN_HTTPS=${API_LISTEN_HTTPS:-no}
API_HTTPS_PORT=${API_HTTPS_PORT:-5443}
API_SERVER_NAME=${API_SERVER_NAME:-bwapi}
API_WHITELIST_IP=${API_WHITELIST_IP:-127.0.0.0/8}
API_TOKEN=${API_TOKEN:-}
USE_REAL_IP=${USE_REAL_IP:-no}
USE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL:-no}
REAL_IP_FROM=${REAL_IP_FROM:-192.168.0.0/16 172.16.0.0/12 10.0.0.0/8}
REAL_IP_HEADER=${REAL_IP_HEADER:-X-Forwarded-For}
HTTP_PORT=${HTTP_PORT:-8080}
HTTPS_PORT=${HTTPS_PORT:-8443}
KEEP_CONFIG_ON_RESTART=${KEEP_CONFIG_ON_RESTART:-no}
EOF
}

function set_loading_state() {
	local nginx_variables_path="$1"
	if [ ! -f "$nginx_variables_path" ] ; then
		return 1
	fi

	if grep -q "^IS_LOADING=" "$nginx_variables_path" ; then
		sed -i "s/^IS_LOADING=.*/IS_LOADING=yes/" "$nginx_variables_path"
	else
		echo "IS_LOADING=yes" >> "$nginx_variables_path"
	fi

	return 0
}

# generate "temp" config
tmp_env_path="/tmp/variables.env"
tmp_env_content="$(generate_tmp_env_content)"
regenerate_temp_config=false

if [[ "$KEEP_CONFIG_ON_RESTART" == "no" ]] || [[ ! -f "$tmp_env_path" ]] ; then
	regenerate_temp_config=true
else
	log "ENTRYPOINT" "ℹ️" "Preserving current config on restart, forcing loading state to receive latest config ..."
	if ! set_loading_state "/etc/nginx/variables.env" ; then
		log "ENTRYPOINT" "⚠️" "Couldn't set IS_LOADING=yes because /etc/nginx/variables.env is missing"
	fi
fi

printf "%s\n" "$tmp_env_content" > "$tmp_env_path"

if [[ "$regenerate_temp_config" == "true" ]] ; then
  python3 /usr/share/bunkerweb/gen/main.py --variables "$tmp_env_path"
fi

if [ -f /var/tmp/bunkerweb_reloading ] ; then
	rm -f /var/tmp/bunkerweb_reloading
fi

# start nginx
log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
nginx -g "daemon off;" &
pid="$!"

# wait while nginx is running
wait "$pid"
while [ -f "/var/run/bunkerweb/nginx.pid" ] ; do
	wait "$pid"
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb stopped"
exit 0
