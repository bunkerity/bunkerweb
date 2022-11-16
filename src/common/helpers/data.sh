#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

log "$1" "ℹ️" "Setup and check /data folder ..."

# Create folders if missing and check permissions
rwx_folders=("cache" "cache/letsencrypt" "lib")
rx_folders=("configs" "configs/http" "configs/stream" "configs/server-http" "configs/server-stream" "configs/default-server-http" "configs/default-server-stream" "configs/modsec" "configs/modsec-crs" "plugins" "www")
for folder in "${rwx_folders[@]}" ; do
	if [ ! -d "/data/${folder}" ] ; then
		mkdir -p "/data/${folder}"
		if [ $? -ne 0 ] ; then
			log "$1" "❌" "Wrong permissions on /data (RWX needed for user nginx with uid 101 and gid 101)"
			exit 1
		fi
	elif [ ! -r "/data/${folder}" ] || [ ! -w "/data/${folder}" ] || [ ! -x "/data/${folder}" ] ; then
		log "$1" "❌" "Wrong permissions on /data/${folder} (RWX needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done
for folder in "${rx_folders[@]}" ; do
	if [ ! -d "/data/${folder}" ] ; then
		mkdir -p "/data/${folder}"
		if [ $? -ne 0 ] ; then
			log "$1" "❌" "Wrong permissions on /data (RWX needed for user nginx with uid 101 and gid 101)"
			exit 1
		fi
	elif [ ! -r "/data/${folder}" ] || [ ! -x "/data/${folder}" ] ; then
		log "$1" "❌" "Wrong permissions on /data/${folder} (RX needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done
# Check permissions on files
IFS=$'\n'
for file in $(find /data -type f) ; do
	if [ ! -r "${file}" ] ; then
		log "$1" "❌" "Wrong permissions on ${file} (at least R needed for user nginx with uid 101 and gid 101)"
		exit 1
	fi
done