#!/bin/bash

# load default values
. ./opt/entrypoint/defaults.sh

echo "[*] Starting bunkerized-nginx ..."

# trap SIGTERM and SIGINT
function trap_exit() {
	echo "[*] Catched stop operation"
	echo "[*] Stopping crond ..."
	pkill -TERM crond
	echo "[*] Stopping nginx ..."
	/usr/sbin/nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	echo "[*] Catched reload operation"
	if [ "$MULTISITE" = "yes" ] && [ "$SWARM_MODE" != "yes" ] ; then
		/opt/entrypoint/multisite-config.sh
	fi
	if [ -f /tmp/nginx.pid ] ; then
		echo "[*] Reloading nginx ..."
		nginx -s reload
		if [ $? -eq 0 ] ; then
			echo "[*] Reload successfull"
		else
			echo "[!] Reload failed"
		fi
	else
		echo "[!] Ignored reload operation because nginx is not running"
	fi
}
trap "trap_reload" HUP

# do the configuration magic if needed
if [ ! -f "/opt/installed" ] ; then

	echo "[*] Configuring bunkerized-nginx ..."

	# check permissions
	if [ "$SWARM_MODE" = "no" ] ; then
		/opt/entrypoint/permissions.sh
	else
		/opt/entrypoint/permissions-swarm.sh
	fi
	if [ "$?" -ne 0 ] ; then
		exit 1
	fi

	# lua config
	# TODO : move variables from /usr/local/lib/lua + multisite support ?
	/opt/entrypoint/lua.sh

	# clamav config
	/opt/entrypoint/clamav.sh

	# start temp nginx to solve Let's Encrypt challenges if needed
	/opt/entrypoint/nginx-temp.sh

	# only do config if we are not in swarm mode
	if [ "$SWARM_MODE" = "no" ] ; then
		# global config
		/opt/entrypoint/global-config.sh
		# background jobs
		/opt/entrypoint/jobs.sh
		# multisite configs
		if [ "$MULTISITE" = "yes" ] ; then
			for server in $SERVER_NAME ; do
				/opt/entrypoint/site-config.sh "$server"
				echo "[*] Multi site - $server configuration done"
			done
			/opt/entrypoint/multisite-config.sh
		# singlesite config
		else
			/opt/entrypoint/site-config.sh
			echo "[*] Single site - $SERVER_NAME configuration done"
		fi
	fi

	touch /opt/installed
else
	echo "[*] Skipping configuration process"
fi

# start crond
crond

# wait until config has been generated if we are in swarm mode
if [ "$SWARM_MODE" = "yes" ] ; then
	echo "[*] Waiting until config has been generated ..."
	while [ ! -f "/etc/nginx/autoconf" ] ; do
		sleep 1
	done
fi

# stop temp config if needed
if [ -f "/tmp/nginx-temp.pid" ] ; then
	nginx -c /tmp/nginx-temp.conf -s quit
fi

# run nginx
echo "[*] Running nginx ..."
nginx &
pid="$!"
#if [ "$?" -eq 0 ] ; then
#	echo "[*] nginx successfully started !"
#else
#	echo "[!] nginx failed to start"
#fi

# autotest
if [ "$1" == "test" ] ; then
	sleep 10
	echo -n "autotest" > /www/index.html
	check=$(curl "http://localhost:${HTTP_PORT}" 2> /dev/null)
	if [ "$check" == "autotest" ] ; then
		exit 0
	fi
	exit 1
fi

# wait for nginx
wait "$pid"
while [ -f "/tmp/nginx.pid" ] ; do
	wait "$pid"
done

# sigterm trapped
echo "[*] bunkerized-nginx stopped"
exit 0
