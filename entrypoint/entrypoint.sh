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
trap "trap_exit" TERM INT

# trap SIGHUP
function trap_reload() {
	echo "[*] Catched reload operation"
	if [ "$MULTISITE" = "yes" ] ; then
		/opt/entrypoint/multisite-config.sh
	fi
	if [ -f /tmp/nginx.pid ] ; then
		echo "[*] Reloading nginx ..."
		/usr/sbin/nginx -s reload
		if [ $? -eq 0 ] ; then
			echo "[*] Reload succesfull"
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
	/opt/entrypoint/global-config.sh
	if [ "$MULTISITE" = "yes" ] ; then
		for server in $SERVER_NAME ; do
			/opt/entrypoint/site-config.sh "$server"
			echo "[*] Multi site - $server configuration done"
		done
		/opt/entrypoint/multisite-config.sh
	else
		/opt/entrypoint/site-config.sh
		echo "[*] Single site - $SERVER_NAME configuration done"
	fi
	touch /opt/installed
else
	echo "[*] Skipping configuration process"
fi

# fix nginx configs rights (and modules through the symlink)
chown -R root:nginx /etc/nginx/
chmod -R 740 /etc/nginx/
find /etc/nginx -type d -exec chmod 750 {} \;

# start rsyslogd
rsyslogd

# start crond
crond

# start nginx
if [ -f "/tmp/nginx-temp.pid" ] ; then
	nginx -c /etc/nginx/nginx-temp.conf -s quit
fi
echo "[*] Running nginx ..."
su -s "/usr/sbin/nginx" nginx

# list of log files to display
LOGS="/var/log/access.log /var/log/error.log /var/log/jobs.log"

# start fail2ban
if [ "$USE_FAIL2BAN" = "yes" ] ; then
	echo "[*] Running fail2ban ..."
	fail2ban-server > /dev/null
	LOGS="$LOGS /var/log/fail2ban.log"
fi

# start crowdsec
if [ "$USE_CROWDSEC" = "yes" ] ; then
	echo "[*] Running crowdsec ..."
	crowdsec
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
wait $!

# sigterm trapped
echo "[*] bunkerized-nginx stopped"
exit 0
