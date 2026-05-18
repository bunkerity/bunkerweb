#!/bin/bash

# Ensure common FreeBSD/Linux local binary paths are available in non-interactive contexts
# (e.g. pkg post-install scripts, rc.d service execution).
if ! echo ":$PATH:" | grep -q ":/usr/local/bin:"; then
	export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
fi

# Helper to find the highest available Python binary
function get_python_bin() {
	local python_bin="/usr/local/bin/python3"

	resolve_python_cmd() {
		local candidate="$1"
		if command -v "$candidate" >/dev/null 2>&1; then
			command -v "$candidate"
			return 0
		fi
		for prefix in /usr/local/bin /usr/bin /bin; do
			if [ -x "${prefix}/${candidate}" ]; then
				echo "${prefix}/${candidate}"
				return 0
			fi
		done
		return 1
	}

	# Prefer the interpreter version used to build bundled deps (deduced from compiled wheels)
	local deps_path="/usr/share/bunkerweb/deps/python"
	if [ -d "$deps_path" ]; then
		local abi_tag
		abi_tag=$(
			find "$deps_path" -maxdepth 2 -type f -name "*cpython-3*.so" 2>/dev/null \
			| sed -nE 's/.*cpython-(3[0-9]{2}).*/\1/p' \
			| sort -r \
			| head -n 1
		)

		if [ -n "$abi_tag" ]; then
			local deps_version="3.${abi_tag:1}"
			if resolved_python=$(resolve_python_cmd "python${deps_version}"); then
				echo "$resolved_python"
				return
			fi
		fi
	fi

	for version in 3.13 3.12 3.11 3.10 3.9; do
		if resolved_python=$(resolve_python_cmd "python${version}"); then
			echo "$resolved_python"
			return
		fi
	done

	if resolved_python=$(resolve_python_cmd "python3"); then
		echo "$resolved_python"
		return
	fi

	echo "$python_bin"
}

# Resolve the Python site-packages path used by BunkerWeb packaging.
function get_bunkerweb_pythonpath() {
	if [ -d /usr/share/bunkerweb/deps/python ]; then
		echo "/usr/share/bunkerweb/deps/python"
		return
	fi
	if [ -d /usr/share/bunkerweb/deps ]; then
		echo "/usr/share/bunkerweb/deps"
		return
	fi
	echo "/usr/share/bunkerweb/deps/python"
}

# Resolve nginx binary path across Linux and FreeBSD.
function get_nginx_bin() {
	if command -v nginx >/dev/null 2>&1; then
		command -v nginx
		return
	fi
	if [ -x /usr/sbin/nginx ]; then
		echo "/usr/sbin/nginx"
		return
	fi
	echo "/usr/local/sbin/nginx"
}

# Resolve nginx config directory across Linux and FreeBSD.
function get_nginx_conf_dir() {
	if [ "$(uname)" = "FreeBSD" ] && [ -d /usr/local/etc/nginx ]; then
		echo "/usr/local/etc/nginx"
		return
	fi

	if [ -d /etc/nginx ]; then
		if [ -L /etc/nginx ]; then
			local nginx_target
			nginx_target=$(readlink /etc/nginx 2>/dev/null)
			if [ -n "$nginx_target" ]; then
				case "$nginx_target" in
					/*)
						[ -d "$nginx_target" ] && { echo "$nginx_target"; return; }
						;;
					*)
						[ -d "/etc/${nginx_target}" ] && { echo "/etc/${nginx_target}"; return; }
						;;
				esac
			fi
		fi
		echo "/etc/nginx"
		return
	fi

	if [ -d /usr/local/etc/nginx ]; then
		echo "/usr/local/etc/nginx"
		return
	fi

	echo "/etc/nginx"
}

# Export key/value pairs from a simple env file (KEY=VALUE lines).
function export_env_file() {
	local env_file=$1
	[ -f "$env_file" ] || return 0
	while IFS='=' read -r key value; do
		[[ -z "$key" || "$key" =~ ^# ]] && continue
		key=$(echo "$key" | xargs)
		[[ -z "$key" ]] && continue
		export "$key=$value"
	done < "$env_file"
}

# Execute a command as the nginx user using the safest available helper
function run_as_nginx() {
	if command -v setpriv >/dev/null 2>&1; then
		setpriv --reuid=nginx --regid=nginx --init-groups --inh-caps=-all -- "$@"
		return $?
	fi

	if command -v runuser >/dev/null 2>&1; then
		runuser -u nginx -- "$@"
		return $?
	fi

	if command -v sudo >/dev/null 2>&1; then
		sudo -n -E -u nginx -g nginx -- "$@"
		return $?
	fi

	if command -v su >/dev/null 2>&1; then
		local cmd_escaped
		cmd_escaped=$(printf "%q " "$@")
		su -m nginx -c "$cmd_escaped"
		return $?
	fi

	return 1
}

# check rx or rwx permissions on a folder
function check_permissions() {
	if [ "$1" = "rx" ] ; then
		[ -r "$2" ] && [ -x "$2" ]
		return $?
	fi
	[ -r "$2" ] && [ -x "$2" ] && [ -w "$2" ]
	return $?
}

# replace pattern in file
function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed "s/$pattern/$replace/g" "$1" > /tmp/sed
	cat /tmp/sed > "$1"
	rm /tmp/sed
}

# convert space separated values to LUA
function spaces_to_lua() {
	for element in $1 ; do
		if [ "$result" = "" ] ; then
			result="\"${element}\""
		else
			result="${result}, \"${element}\""
		fi
	done
	echo "$result"
}

# convert size value (bytes or human-readable) to bytes
# supported units: B, K, KB, KiB, M, MB, MiB, G, GB, GiB, T, TB, TiB
function parse_size_to_bytes() {
	local raw_value="$1"
	local normalized number unit multiplier bytes

	normalized=$(echo "$raw_value" | tr -d '[:space:]')
	[ -n "$normalized" ] || return 1

	if [[ ! "$normalized" =~ ^([0-9]+([.][0-9]+)?)([A-Za-z]*)$ ]]; then
		return 1
	fi

	number="${BASH_REMATCH[1]}"
	unit=$(echo "${BASH_REMATCH[3]}" | tr '[:upper:]' '[:lower:]')

	case "$unit" in
		"" | "b") multiplier=1 ;;
		"k" | "kb" | "ki" | "kib") multiplier=1024 ;;
		"m" | "mb" | "mi" | "mib") multiplier=$((1024 * 1024)) ;;
		"g" | "gb" | "gi" | "gib") multiplier=$((1024 * 1024 * 1024)) ;;
		"t" | "tb" | "ti" | "tib") multiplier=$((1024 * 1024 * 1024 * 1024)) ;;
		*) return 1 ;;
	esac

	bytes=$(awk -v value="$number" -v factor="$multiplier" 'BEGIN {
		result = value * factor
		if (result <= 0) {
			print 0
		} else {
			printf "%d", result
		}
	}')

	if [[ ! "$bytes" =~ ^[0-9]+$ ]] || [ "$bytes" -le 0 ]; then
		return 1
	fi

	echo "$bytes"
}

# check if at least one env var (global or multisite) has a specific value
function has_value() {
	nginx_conf_dir=$(get_nginx_conf_dir)
	[ -d "$nginx_conf_dir" ] || return 0
	envs=$(find "$nginx_conf_dir" -name "*.env")
	for file in $envs ; do
		if [ "$(grep "^${1}=${2}$" "$file")" != "" ] ; then
			echo "$file"
		fi
	done
}

# log to stdout
function log() {
	when="$(date '+[%Y-%m-%d %H:%M:%S]')"
	category="$1"
	severity="$2"
	message="$3"
	echo "$when - $category - $severity - $message"
}

# get only interesting env (var=value)
function get_env() {
for var_name in $(python3 -c 'import os ; [print(k) for k in os.environ]') ; do
	filter=$(echo -n "$var_name" | sed -r 's/^(HOSTNAME|PWD|PKG_RELEASE|NJS_VERSION|SHLVL|PATH|_|NGINX_VERSION|HOME|([0-9a-z\.\-]*)_?CUSTOM_CONF_(HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(.*))$//g')
	if [ "$filter" != "" ] ; then
        var_value=$(python3 -c "import os ; print(os.environ['${var_name}'])")
		echo "${var_name}=${var_value}"
	fi
done
}

# Function to handle Docker secrets
function handle_docker_secrets() {
	local secrets_dir="/run/secrets"
	if [ -d "$secrets_dir" ]; then
		log "ENTRYPOINT" "ℹ️" "Processing Docker secrets from $secrets_dir ..."
		for secret_file in "$secrets_dir"/*; do
			if [ -f "$secret_file" ]; then
				local secret_name
				secret_name=$(basename "$secret_file")
				local secret_value
				secret_value=$(cat "$secret_file")
				# Export the secret as an environment variable (uppercase)
				export "${secret_name^^}"="$secret_value"
				log "ENTRYPOINT" "ℹ️" "Loaded Docker secret: ${secret_name^^}"
			fi
		done
	fi
}

# ============================================================================
# Cross-platform init system detection and service management
# Supports: systemd (Linux), rc.d (FreeBSD)
# ============================================================================

# Detect the init system in use
# Returns: "systemd", "rcd", or "unknown"
function detect_init_system() {
	if [ "$(uname)" = "FreeBSD" ]; then
		echo "rcd"
		return
	fi
	if command -v systemctl >/dev/null 2>&1 && systemctl --version >/dev/null 2>&1; then
		echo "systemd"
		return
	fi
	# Fallback check for rc.d (FreeBSD-style)
	if [ -d /usr/local/etc/rc.d ] || [ -d /etc/rc.d ]; then
		echo "rcd"
		return
	fi
	echo "unknown"
}

# Convert service name for rc.d (replace hyphens with underscores)
function rcd_service_name() {
	echo "$1" | tr '-' '_'
}

# Return the rc.conf.d file path for a given rc.d service.
function rcd_conf_file() {
	echo "/etc/rc.conf.d/$1"
}

# Check if a service is enabled
function service_is_enabled() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl is-enabled --quiet "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name rcd_conf enabled_value
			rcd_name=$(rcd_service_name "$service_name")
			rcd_conf=$(rcd_conf_file "$rcd_name")
			if [ -f "$rcd_conf" ]; then
				enabled_value=$(sysrc -f "$rcd_conf" -n "${rcd_name}_enable" 2>/dev/null || true)
				echo "$enabled_value" | grep -qi "yes"
				return $?
			fi
			sysrc -n "${rcd_name}_enable" 2>/dev/null | grep -qi "yes"
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Check if a service is currently running
function service_is_running() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl is-active --quiet "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			service "$rcd_name" status >/dev/null 2>&1
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Enable a service (set to start on boot)
function service_enable() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl enable "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name rcd_conf
			rcd_name=$(rcd_service_name "$service_name")
			rcd_conf=$(rcd_conf_file "$rcd_name")
			mkdir -p /etc/rc.conf.d
			sysrc -f "$rcd_conf" "${rcd_name}_enable=YES" >/dev/null 2>&1
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Disable a service (do not start on boot)
function service_disable() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl disable "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name rcd_conf
			rcd_name=$(rcd_service_name "$service_name")
			rcd_conf=$(rcd_conf_file "$rcd_name")
			mkdir -p /etc/rc.conf.d
			sysrc -f "$rcd_conf" "${rcd_name}_enable=NO" >/dev/null 2>&1
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Start a service
function service_start() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl start "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			service "$rcd_name" start 2>/dev/null
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Stop a service
function service_stop() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl stop "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			service "$rcd_name" stop 2>/dev/null
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Restart a service
function service_restart() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl restart "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			service "$rcd_name" restart 2>/dev/null
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Reload a service (if supported) or restart
function service_reload() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl reload "$service_name" 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			# Try reload, fall back to restart
			service "$rcd_name" reload 2>/dev/null || service "$rcd_name" restart 2>/dev/null
			return $?
			;;
		*)
			return 1
			;;
	esac
}

# Enable and start a service in one call
function service_enable_now() {
	local service_name="$1"
	service_enable "$service_name" && service_start "$service_name"
	return $?
}

# Disable and stop a service in one call
function service_disable_now() {
	local service_name="$1"
	service_stop "$service_name"
	service_disable "$service_name"
	return $?
}

# Get service status (for display purposes)
function service_status() {
	local service_name="$1"
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl status "$service_name" --no-pager -l 2>/dev/null
			return $?
			;;
		rcd)
			local rcd_name
			rcd_name=$(rcd_service_name "$service_name")
			service "$rcd_name" status 2>/dev/null
			return $?
			;;
		*)
			echo "Unknown init system"
			return 1
			;;
	esac
}

# Reload init system configuration (systemd daemon-reload equivalent)
function init_reload_config() {
	local init_system
	init_system=$(detect_init_system)

	case "$init_system" in
		systemd)
			systemctl daemon-reload 2>/dev/null
			return $?
			;;
		rcd)
			# rc.d doesn't need a daemon-reload equivalent
			return 0
			;;
		*)
			return 1
			;;
	esac
}
