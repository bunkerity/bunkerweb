#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm repo add mattermost https://helm.mattermost.com
helm install mattermost mattermost/mattermost-team-edition
