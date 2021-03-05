#!/bin/bash

# replace pattern in file
function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
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
	if [ "${!1}" == "$2" ] ; then
		echo "ok"
		return 0
	fi
	for var in $(compgen -e) ; do
		domain=$(echo "$var" | cut -d '_' -f 1)
		name=$(echo "$var" | cut -d '=' -f 1 | sed "s~${domain}_~~")
		value=$(echo "${!var}")
		if [ "$name" == "$1" ] && [ "$value" == "$2" ] ; then
			echo "ok"
			return 0
		fi
	done
}
