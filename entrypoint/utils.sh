#!/bin/bash

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
	if [ -f "/etc/nginx/site.env" ] ; then
		if [ $(grep "^${1}=${2}$" /etc/nginx/site.env) != "" ] ; then
			echo "ok"
			return 0
		fi
	else
		servers=$(find /etc/nginx -name "site.env" | cut -d '/' -f 4)
		for server in $servers ; do
			if [ $(grep "^${1}=${2}$" /etc/nginx/$server/site.env) != "" ] ; then
				echo "ok"
				return 0
			fi
		done
	fi
}

# log to jobs.log
function job_log() {
	when="$(date '+[%Y-%m-%d %H:%M:%S]')"
	what="$1"
	echo "$when $what" >> /var/log/jobs.log
}
