#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
	if [ -f "/var/run/bunkerweb/ui.pid" ] ; then
		log "ENTRYPOINT" "ℹ️ " "Stopping UI ..."
		kill -s TERM "$(cat /var/run/bunkerweb/ui.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/ui.pid ] ; then
	rm -f /var/run/bunkerweb/ui.pid
fi

log "ENTRYPOINT" "ℹ️ " "Starting the UI v$(cat /usr/share/bunkerweb/VERSION) ..."

python3 /usr/share/bunkerweb/ui/ui.py

if [ $? == 1 ] ; then
  log "ENTRYPOINT" "❌ " "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
  exit 1
elif [ $? == 2 ] ; then
	log "ENTRYPOINT" "❌ " "Invalid PORT, It must be an integer between 1 and 65535."
  exit 1
fi

set -a # turn on automatic exporting
source /tmp/ui.tmp.env
set +a # turn off automatic exporting

rm -f /tmp/ui.tmp.env

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing UI ..."
node nuxt/.output/server/index.mjs &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/ui.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/ui.healthy ] ; then
	rm /var/tmp/bunkerweb/ui.healthy
fi
log "ENTRYPOINT" "ℹ️ " "UI stopped"
exit 0
