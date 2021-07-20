#!/bin/bash

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
	if [ "$SWARM_MODE" != "yes" ] ; then
		/opt/bunkerized-nginx/entrypoint/pre-jobs.sh
	fi
	if [ -f /tmp/nginx.pid ] ; then
		echo "[*] Reloading nginx ..."
		nginx -s reload
		if [ $? -eq 0 ] ; then
			echo "[*] Reload successfull"
			if [ "$SWARM_MODE" != "yes" ] ; then
				/opt/bunkerized-nginx/entrypoint/post-jobs.sh
			fi
		else
			echo "[!] Reload failed"
		fi
	else
		echo "[!] Ignored reload operation because nginx is not running"
	fi
}
trap "trap_reload" HUP

# do the configuration magic if needed
if [ ! -f "/etc/nginx/global.env" ] ; then

	echo "[*] Configuring bunkerized-nginx ..."

	# check permissions
	if [ "$SWARM_MODE" != "yes" ] ; then
		/opt/bunkerized-nginx/entrypoint/permissions.sh
	else
		/opt/bunkerized-nginx/entrypoint/permissions-swarm.sh
	fi
	if [ "$?" -ne 0 ] ; then
		exit 1
	fi

	# start temp nginx to solve Let's Encrypt challenges if needed
	/opt/bunkerized-nginx/entrypoint/nginx-temp.sh

	# only do config if we are not in swarm mode
	if [ "$SWARM_MODE" != "yes" ] ; then
		# export the variables
		env | grep -E -v "^(HOSTNAME|PWD|PKG_RELEASE|NJS_VERSION|SHLVL|PATH|_|NGINX_VERSION|HOME)=" > "/tmp/variables.env"

		# call the generator
		/opt/bunkerized-nginx/gen/main.py --settings /opt/bunkerized-nginx/settings.json --templates /opt/bunkerized-nginx/confs --output /etc/nginx --variables /tmp/variables.env

		# jobs
		/opt/bunkerized-nginx/entrypoint/jobs.sh
	fi
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
nginx -g 'daemon off;' &
pid="$!"

# autotest
if [ "$1" == "test" ] ; then
	sleep 10
	echo -n "autotest" > /opt/bunkerized-nginx/www/index.html
	check=$(curl -H "User-Agent: legit" "http://localhost:8080")
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
