#!/bin/bash

if [ "$(id -u)" -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

if [ ! -d ./volumes/app/mattermost ] ; then
	mkdir -p ./volumes/app/mattermost/{config,data,logs,plugins,client/plugins,bleve-indexes}
fi
chown -R 2000:2000 ./volumes/app/mattermost
