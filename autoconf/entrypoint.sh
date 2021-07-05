#!/bin/bash

echo "[*] Starting autoconf ..."

# check permissions
su -s "/opt/bunkerized-nginx/entrypoint/permissions.sh" nginx
if [ "$?" -ne 0 ] ; then
	exit 1
fi

if [ "$SWARM_MODE" = "yes" ] ; then
	chown -R root:nginx /etc/nginx
	chmod -R 770 /etc/nginx
fi

# trap SIGTERM and SIGINT
function trap_exit() {
	echo "[*] Catched stop operation"
	echo "[*] Stopping crond ..."
	pkill -TERM crond
	echo "[*] Stopping autoconf ..."
	pkill -TERM python3
}
trap "trap_exit" TERM INT QUIT

# start cron
crond

# run autoconf app
/opt/bunkerized-nginx/entrypoint/app.py &
pid="$!"

# wait while app is up
wait "$pid"

# stop
echo "[*] autoconf stopped"
exit 0
