#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
	# shellcheck disable=SC2317
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

output="$(python3 /usr/share/bunkerweb/ui/ui.py 2>&1)"
ret=$?

if [ $ret == 1 ] ; then
		# Show the output of the core
		log "ENTRYPOINT" "❌ " "$output"
		exit 1
elif [ $ret == 2 ] ; then
		log "ENTRYPOINT" "❌ " "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
		exit 1
elif [ $ret == 3 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid PORT, It must be an integer between 1 and 65535."
		exit 1
fi

set -a # turn on automatic exporting
source /etc/bunkerweb/ui.env
set +a # turn off automatic exporting

# execute ui
log "ENTRYPOINT" "ℹ️ " "Executing UI ..."
python3 -m gunicorn --config /usr/share/bunkerweb/ui/gunicorn.conf.py --bind "$LISTEN_ADDR":"$LISTEN_PORT" --log-level "$LOG_LEVEL" --forwarded-allow-ips "$REVERSE_PROXY_IPS" --proxy-allow-from "$REVERSE_PROXY_IPS" &
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
