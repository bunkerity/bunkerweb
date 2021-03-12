#!/bin/bash

echo "[*] Starting autoconf ..."

cp /opt/confs/nginx/* /etc/nginx

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

# run autoconf app
/opt/entrypoint/app.py &

# display logs
tail -F /var/log/jobs.log &
pid="$!"
wait "$pid"

# stop
echo "[*] autoconf stopped"
exit 0
