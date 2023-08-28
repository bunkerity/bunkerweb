#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

log "ENTRYPOINT" "ℹ️ " "Starting the autoconf v$(cat /usr/share/bunkerweb/VERSION) ..."

# execute autoconf
log "ENTRYPOINT" "ℹ️ " "Executing Autoconf ..."
python main.py &
pid="$!"
wait "$pid"
while [ -f /var/run/bunkerweb/autoconf.pid ] ; do
    wait "$pid"
done

if [ -f /var/tmp/bunkerweb/autoconf.healthy ] ; then
	rm /var/tmp/bunkerweb/autoconf.healthy
fi
log "ENTRYPOINT" "ℹ️ " "Autoconf stopped"
exit 0
