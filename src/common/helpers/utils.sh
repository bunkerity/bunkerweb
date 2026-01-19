#!/bin/bash

# Helper to find the highest available Python binary
function get_python_bin() {
	local python_bin="python3"

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
			if command -v "python${deps_version}" >/dev/null 2>&1; then
				echo "python${deps_version}"
				return
			fi
		fi
	fi

	for version in 3.13 3.12 3.11 3.10 3.9; do
		if command -v "python${version}" >/dev/null 2>&1; then
			python_bin="python${version}"
			break
		fi
	done

	echo "$python_bin"
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

# check if at least one env var (global or multisite) has a specific value
function has_value() {
	envs=$(find /etc/nginx -name "*.env")
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
