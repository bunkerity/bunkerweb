#!/bin/bash

echo "[*] Starting autoconf ..."

# check permissions
su -s "/opt/entrypoint/permissions.sh" nginx
if [ "$?" -ne 0 ] ; then
	exit 1
fi

if [ "$SWARM_MODE" = "yes" ] ; then
	cp -r /opt/confs/nginx/* /etc/nginx
	chown -R root:nginx /etc/nginx
	chmod -R 770 /etc/nginx
fi

# trap SIGTERM and SIGINT
function trap_exit() {
	echo "[*] Catched stop operation"
	echo "[*] Stopping crond ..."
	pkill -TERM crond
	echo "[*] Stopping python3 ..."
	pkill -TERM python3
	pkill -TERM tail
}
trap "trap_exit" TERM INT QUIT

# remove old crontabs
echo "" > /etc/crontabs/root

# setup logrotate
touch /var/log/jobs.log
echo "0 0 * * * /usr/sbin/logrotate -f /etc/logrotate.conf > /dev/null 2>&1" >> /etc/crontabs/root

# start cron
crond

# run autoconf app
/opt/entrypoint/app.py &

# display logs
tail -F /var/log/jobs.log &
pid="$!"
wait "$pid"

# stop
echo "[*] autoconf stopped"
exit 0
