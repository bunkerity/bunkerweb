#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh
service="$1"

log "$service" "ℹ️" "Setup and check /data folder ..."

# Create folders if missing and check permissions
rwx_folders=("cache" "cache/letsencrypt" "lib")
rx_folders=("pro" "pro/plugins" "configs" "configs/http" "configs/stream" "configs/server-http" "configs/server-stream" "configs/default-server-http" "configs/default-server-stream" "configs/modsec" "configs/modsec-crs" "configs/crs-plugins-before" "configs/crs-plugins-after" "plugins" "www")
for folder in "${rwx_folders[@]}" ; do
	if [ ! -d "/data/${folder}" ] ; then
		mkdir -p "/data/${folder}"
		# shellcheck disable=SC2181
		if [ $? -ne 0 ] ; then
			log "$service" "❌" "Wrong permissions on /data (RWX needed for user nginx with uid 101 and gid 101)"
			exit 1
		fi
	elif [ ! -r "/data/${folder}" ] || [ ! -w "/data/${folder}" ] || [ ! -x "/data/${folder}" ] ; then
		log "$service" "❌" "Wrong permissions on /data/${folder} (RWX needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done
for folder in "${rx_folders[@]}" ; do
	if [ ! -d "/data/${folder}" ] ; then
		mkdir -p "/data/${folder}"
		# shellcheck disable=SC2181
		if [ $? -ne 0 ] ; then
			log "$service" "❌" "Wrong permissions on /data (RWX needed for user nginx with uid 101 and gid 101)"
			exit 1
		fi
	elif [ ! -r "/data/${folder}" ] || [ ! -x "/data/${folder}" ] ; then
		log "$service" "❌" "Wrong permissions on /data/${folder} (RX needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done

# Check permissions on files
IFS=$'\n'
shopt -s globstar
for file in /data/**/*; do
	if [[ -f "$file" ]] && [[ ! -r "$file" ]] ; then
		log "$service" "❌" "Wrong permissions on ${file} (at least R needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done
