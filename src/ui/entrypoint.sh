#!/bin/bash
set -e

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

log "ENTRYPOINT" "ℹ️" "Starting the web UI v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
else
  echo "Docker" > /usr/share/bunkerweb/INTEGRATION
fi

python3 -m gunicorn --config gunicorn.conf.py --user ui --group ui --bind 0.0.0.0:7000

log "ENTRYPOINT" "ℹ️" "Web UI stopped"
exit 0
