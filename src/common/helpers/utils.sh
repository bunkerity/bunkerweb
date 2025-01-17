#!/bin/bash

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
