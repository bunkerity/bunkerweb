#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

if [[ $(echo "${SKIP_ASCII_BANNER:-no}" | awk '{print tolower($0)}') != "yes" ]] ; then
	shopt -s nullglob
	ascii_array=(/usr/share/bunkerweb/misc/*.ascii)
	shopt -u nullglob
	if [ ${#ascii_array[@]} -gt 0 ] ; then
		cat "${ascii_array[$((RANDOM % ${#ascii_array[@]}))]}"
	fi
fi

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

# The generator installs a rendered configuration into /etc/nginx file by file, and a reload reads the
# routing and the variables at different moments, so a signal that lands part way through an install
# loads a mix of two generations. The reload and the generator take turns through two files (see
# lua/bunkerweb/api.lua and gen/sync_tree.py): the generator locks /var/tmp/bunkerweb/generating and then
# looks for the reloading marker, the reload creates the marker and then probes the lock, so whoever
# comes second sees the other one and backs off.
# Succeeds while a generator holds its lock. The busybox flock has no exit code of its own for a held
# lock, so a lock that cannot be probed counts as held and the reload does not go on.
# shellcheck disable=SC2329
function generator_installing() {
	[ -e /var/tmp/bunkerweb/generating ] || return 1
	# Opened for reading only, so this never creates the file. The shared lock is taken without waiting
	# and given back when the subshell exits.
	if ( exec 9< /var/tmp/bunkerweb/generating && flock -n -s 9 ) 2>/dev/null ; then
		return 1
	fi
}

# Publishes the reloading marker holding a token: the token is written to a file of its own and hard
# linked to the marker, which fails while the marker exists. The marker is therefore either absent or
# complete, and a write that fails (disk full, file size limit) leaves nothing behind. Returns 0 when
# the marker is published, 1 when it is not (it exists), 2 when the token cannot be written. The write
# runs in a subshell because a file size limit kills the writer with a signal.
# shellcheck disable=SC2329
function publish_marker() {
	local tmp="/var/tmp/bunkerweb/reloading.$$" rc=0
	if ! ( printf "%s" "$reload_token" > "$tmp" ) 2>/dev/null ; then
		rm -f "$tmp"
		return 2
	fi
	ln "$tmp" /var/tmp/bunkerweb/reloading 2>/dev/null || rc=$?
	rm -f "$tmp"
	return "$rc"
}

# Integer seconds since boot, shared with the API and generator and unaffected by wall-clock steps.
# shellcheck disable=SC2329
function read_reload_uptime() {
	local uptime
	IFS=' ' read -r uptime _ 2>/dev/null < /proc/uptime || return 1
	[[ "$uptime" =~ ^([0-9]+)\.[0-9]+$ ]] || return 1
	printf '%s' "${BASH_REMATCH[1]}"
}

# Removes a rejected reload's orphan only when its monotonic stamp proves it is over five minutes old.
# shellcheck disable=SC2329
function clear_stale_reload_marker() {
	local -r RELOAD_MARKER_MAX_AGE=300
	local token current created now
	[ -f /var/tmp/bunkerweb/reloading ] || return 1
	# The suffix preserves trailing newlines so the second read compares the complete content.
	token="$(cat /var/tmp/bunkerweb/reloading && printf '.')" || return 1
	token="${token%.}"
	[[ "$token" =~ ^[0-9]+\.[0-9]+\.([0-9]+)$ ]] || return 1
	created="${BASH_REMATCH[1]}"
	now="$(read_reload_uptime)" || return 1
	awk -v now="$now" -v created="$created" -v age="$RELOAD_MARKER_MAX_AGE" 'BEGIN { exit !(now - created > age) }' || return 1
	current="$(cat /var/tmp/bunkerweb/reloading && printf '.')" || return 1
	# ponytail: two removers and a fresh publisher can still race between this comparison and unlink.
	[ "${current%.}" = "$token" ] || return 1
	rm -f /var/tmp/bunkerweb/reloading || return 1
	log "$1" "⚠️" "Removing orphaned reload marker /var/tmp/bunkerweb/reloading older than 5 minutes"
}

# Creates the reloading marker exclusively holding a token, the way the API reload does: the
# new workers remove it, and only while it still holds the token of the reload they belong to. A marker
# that never goes belongs to a reload nginx rejected after it parsed the configuration.
# Returns 1 while a generator installs, 2 when the marker cannot be published, 3 while another reload is
# in flight: in each case the signal must not go out. Waits reload_wait_ticks tenths of a second, which
# stays under the ten seconds docker gives a stop: the shell runs no other trap meanwhile.
# shellcheck disable=SC2329
function begin_reload() {
	local rc=1 publish_misses=0 uptime
	reload_token="$(date +%s).$RANDOM"
	if uptime="$(read_reload_uptime)" ; then
		reload_token="$reload_token.$uptime"
	fi
	for _ in $(seq 1 "${reload_wait_ticks:-80}") ; do
		clear_stale_reload_marker "ENTRYPOINT"
		# Something that is not a file in the marker's place is no marker, and nothing can take its place
		if [ -e /var/tmp/bunkerweb/reloading ] && [ ! -f /var/tmp/bunkerweb/reloading ] ; then
			return 2
		fi
		publish_marker
		case $? in
			0)
				publish_misses=0
				generator_installing || return 0
				rm -f /var/tmp/bunkerweb/reloading
				rc=1
				;;
			1)
				if [ -e /var/tmp/bunkerweb/reloading ] ; then
					publish_misses=0
				else
					publish_misses=$((publish_misses + 1))
					[ "$publish_misses" -lt 2 ] || return 2
				fi
				rc=3
				;;
			*) return 2 ;;
		esac
		sleep 0.1
	done
	return "$rc"
}

# trap SIGHUP
# shellcheck disable=SC2329
function trap_reload() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️" "Caught reload operation"
	# shellcheck disable=SC2317
	if [ -f /var/run/bunkerweb/nginx.pid ] ; then
		begin_reload
		# shellcheck disable=SC2317
		case $? in
			0) ;;
			2)
				log "ENTRYPOINT" "❌" "Couldn't create /var/tmp/bunkerweb/reloading, keeping running configuration"
				return 1
				;;
			3)
				log "ENTRYPOINT" "❌" "A reload is in progress (/var/tmp/bunkerweb/reloading exists), keeping running configuration. If none is running, the last one was rejected after its configuration was parsed: a marker with a monotonic stamp is cleared automatically once it is older than 5 minutes; restart BunkerWeb or remove that file to clear it sooner"
				return 1
				;;
			*)
				log "ENTRYPOINT" "❌" "A configuration generation is in progress, keeping running configuration"
				return 1
				;;
		esac
		if ! python3 /usr/share/bunkerweb/utils/modsecurity_audit.py /etc/nginx/variables.env ; then
			log "ENTRYPOINT" "❌" "Invalid ModSecurity audit storage, keeping running configuration"
			rm -f /var/tmp/bunkerweb/reloading
			return 1
		fi
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️" "Reloading nginx ..."
		nginx -s reload
		# shellcheck disable=SC2181,SC2317
		if [ $? -eq 0 ] ; then
			log "ENTRYPOINT" "ℹ️" "Reload successful"
		else
			# The marker is ours until the signal went out
			rm -f /var/tmp/bunkerweb/reloading
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

# The scheduler pushes the default server pair and nginx refuses to start on a half or mismatched one.
# The scheduler can only reach this instance through nginx, so a bad pair is replaced here with a
# throwaway one and the next push installs the real one.
function default_pair_is_valid() {
	local cert_pub key_pub
	cert_pub="$(openssl x509 -noout -pubkey -in "$1" 2>/dev/null)" || return 1
	key_pub="$(openssl pkey -pubout -in "$2" 2>/dev/null)" || return 1
	[ -n "$cert_pub" ] && [ "$cert_pub" == "$key_pub" ]
}

default_cert_dir="/var/cache/bunkerweb/misc"
default_cert="$default_cert_dir/default-server-cert.pem"
default_key="$default_cert_dir/default-server-cert.key"
if [ -e "$default_cert" ] || [ -e "$default_key" ] ; then
	if ! default_pair_is_valid "$default_cert" "$default_key" ; then
		log "ENTRYPOINT" "⚠️" "The default server certificate and its private key are missing or do not match, replacing them with a temporary pair until the scheduler pushes the real one"
		tmp_cert="$(mktemp "$default_cert_dir/default-server-cert.XXXXXX")"
		tmp_key="$(mktemp "$default_cert_dir/default-server-cert.XXXXXX")"
		if openssl req -nodes -x509 -newkey ec -pkeyopt ec_paramgen_curve:secp384r1 -keyout "$tmp_key" -out "$tmp_cert" -days 30 -subj "/CN=www.example.org" >/dev/null 2>&1 && default_pair_is_valid "$tmp_cert" "$tmp_key" ; then
			chmod 600 "$tmp_key"
			chmod 644 "$tmp_cert"
			mv -f "$tmp_key" "$default_key"
			mv -f "$tmp_cert" "$default_cert"
			# The cache push is skipped while its applied digest matches the scheduler's archive,
			# so forget it: the next push must reinstall the real pair.
			rm -f /var/tmp/bunkerweb/pushswap/_var_cache_bunkerweb.applied
		else
			rm -f "$tmp_cert" "$tmp_key"
			log "ENTRYPOINT" "❌" "Couldn't generate a temporary default server certificate, nginx may fail to start"
		fi
	fi
fi

# generate "temp" config
tmp_env_path="/tmp/variables.env"
tmp_env_content="$(generate_tmp_env_content)"
regenerate_temp_config=false

# The occurrence above is heredoc content, so it only reaches the generated file and never sets
# the shell variable the test below reads. Unset therefore behaved as "yes" on every restart that
# kept the writable layer, which is the opposite of the documented default.
KEEP_CONFIG_ON_RESTART="${KEEP_CONFIG_ON_RESTART:-no}"

# Present when an install into /etc/nginx was cut short. Each file lands atomically but the tree does
# not, so what is there is a mix of two generations. Keep the name in step with sync_tree.INSTALL_SENTINEL.
install_sentinel="/etc/nginx/.bw-install-incomplete"

if [[ "$KEEP_CONFIG_ON_RESTART" == "no" ]] || [[ ! -f "$tmp_env_path" ]] ; then
	regenerate_temp_config=true
elif [ -e "$install_sentinel" ] ; then
	log "ENTRYPOINT" "⚠️" "The previous configuration install was interrupted, so the preserved config may mix two generations: regenerating the temporary config instead of keeping it"
	regenerate_temp_config=true
else
	log "ENTRYPOINT" "ℹ️" "Preserving current config on restart, keeping it enforced and asking the scheduler for the latest one ..."
	# Every access control keeps running on the preserved configuration. The scheduler sees this
	# file through /health and pushes the latest configuration, which removes it.
	if ! touch /var/tmp/bunkerweb_needs_config ; then
		log "ENTRYPOINT" "⚠️" "Couldn't create /var/tmp/bunkerweb_needs_config, the preserved config stays in use until the next configuration change"
	fi
fi

printf "%s\n" "$tmp_env_content" > "$tmp_env_path"

# A marker left by the previous run stands for no reload: no nginx runs yet. The generator waits for
# it, and refuses to install while it exists, so it has to go first. This also lets the health
# endpoint report "loading" and not a stale "reloading".
if [ -f /var/tmp/bunkerweb/reloading ] ; then
	rm -f /var/tmp/bunkerweb/reloading
fi
# Remove the previous marker location on upgraded hosts; /var/tmp may be read-only.
rm -f /var/tmp/bunkerweb_reloading 2>/dev/null || true

if [[ "$regenerate_temp_config" == "true" ]] ; then
  rm -f /var/tmp/bunkerweb_needs_config
  if ! python3 /usr/share/bunkerweb/gen/main.py --variables "$tmp_env_path" ; then
    log "ENTRYPOINT" "❌" "Error while generating config from $tmp_env_path, refusing to start nginx"
    exit 1
  fi
  rm -f "$install_sentinel"
fi

# Clean orphaned NGINX temp files from previous runs
for dir in client_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp; do
	target="/var/tmp/bunkerweb/$dir"
	if [ -d "$target" ] && [ ! -L "$target" ]; then
		if [ -n "$(find "$target" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
			log "ENTRYPOINT" "ℹ️" "Cleaning orphaned temp files from $dir"
		fi
		find "$target" -mindepth 1 -delete 2>/dev/null || true
	fi
done

# start nginx
if ! python3 /usr/share/bunkerweb/utils/modsecurity_audit.py /etc/nginx/variables.env ; then
	log "ENTRYPOINT" "❌" "Invalid ModSecurity audit storage, refusing to start nginx"
	exit 1
fi
log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
nginx -g "daemon off;" &
pid="$!"

# wait while nginx is running
wait "$pid"
while [ -f "/var/run/bunkerweb/nginx.pid" ] ; do
	# Break if the process is no longer alive (e.g. killed by OOM without cleaning up the PID file)
	kill -0 "$pid" 2>/dev/null || { rm -f "/var/run/bunkerweb/nginx.pid" ; break ; }
	sleep 1
done

log "ENTRYPOINT" "ℹ️" "BunkerWeb stopped"
exit 0
