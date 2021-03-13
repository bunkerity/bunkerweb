#!/bin/bash

# load default values
. ./opt/entrypoint/defaults.sh

echo "[*] Starting bunkerized-nginx ..."

# execute custom scripts if it's a customized image
for file in /entrypoint.d/* ; do
    [ -f "$file" ] && [ -x "$file" ] && "$file"
done

# trap SIGTERM and SIGINT
function trap_exit() {
	echo "[*] Catched stop operation"
	echo "[*] Stopping crond ..."
	pkill -TERM crond
	if [ "$USE_FAIL2BAN" = "yes" ] ; then
		echo "[*] Stopping fail2ban"
		fail2ban-client stop > /dev/null
	fi
	echo "[*] Stopping nginx ..."
	/usr/sbin/nginx -s stop
	echo "[*] Stopping rsyslogd ..."
	pkill -TERM rsyslogd
	pkill -TERM tail
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

	# logs config
	/opt/entrypoint/logs.sh

	# lua config
	# TODO : move variables from /usr/local/lib/lua + multisite support ?
	/opt/entrypoint/lua.sh

	# fail2ban config
	/opt/entrypoint/fail2ban.sh

	# clamav config
	/opt/entrypoint/clamav.sh

	# start temp nginx to solve Let's Encrypt challenges if needed
	/opt/entrypoint/nginx-temp.sh

	# only do config if we are not in swarm mode
	if [ "$SWARM_MODE" = "no" ] ; then
		# global config
		/opt/entrypoint/global-config.sh
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

# start rsyslogd
rsyslogd -i /tmp/rsyslogd.pid

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
nginx
if [ "$?" -eq 0 ] ; then
	echo "[*] nginx successfully started !"
else
	echo "[!] nginx failed to start"
fi

# list of log files to display
LOGS="/var/log/access.log /var/log/error.log /var/log/jobs.log"

# start fail2ban
if [ "$USE_FAIL2BAN" = "yes" ] ; then
	echo "[*] Running fail2ban ..."
	fail2ban-server > /dev/null
	LOGS="$LOGS /var/log/fail2ban.log"
fi

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

# display logs
tail -F $LOGS &
pid="$!"
while [ -f "/tmp/nginx.pid" ] ; do
	wait "$pid"
done

# sigterm trapped
echo "[*] bunkerized-nginx stopped"
exit 0
