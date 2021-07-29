#!/bin/bash

. /opt/bunkerized-nginx/entrypoint/utils.sh

log "entrypoint" "INFO" "starting bunkerized-nginx ..."

# trap SIGTERM and SIGINT
function trap_exit() {
	log "stop" "INFO" "catched stop operation"
	log "stop" "INFO" "stopping crond ..."
	pkill -TERM crond
	log "stop" "INFO" "stopping nginx ..."
	/usr/sbin/nginx -s stop
}
trap "trap_exit" TERM INT QUIT

# trap SIGHUP
function trap_reload() {
	log "reload" "INFO" "catched reload operation"
	if [ "$SWARM_MODE" != "yes" ] ; then
		/opt/bunkerized-nginx/entrypoint/jobs.sh
	fi
	if [ -f /tmp/nginx.pid ] ; then
		log "reload" "INFO" "reloading nginx ..."
		nginx -s reload
		if [ $? -eq 0 ] ; then
			log "reload" "INFO" "reloading successful"
		else
			log "reload" "ERROR" "reloading failed"
		fi
	else
		log "reload" "INFO" "ignored reload operation because nginx is not running"
	fi
}
trap "trap_reload" HUP

# do the configuration magic if needed
if [ ! -f "/etc/nginx/global.env" ] ; then

	log "entrypoint" "INFO" "configuring bunkerized-nginx ..."

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

	# only do config if we are not in swarm/kubernetes mode
	if [ "$SWARM_MODE" != "yes" ] && [ "$KUBERNETES_MODE" != "yes" ] ; then
		# export the variables
		env | grep -E -v "^(HOSTNAME|PWD|PKG_RELEASE|NJS_VERSION|SHLVL|PATH|_|NGINX_VERSION|HOME)=" > "/tmp/variables.env"

		# call the generator
		gen_ret="$(/opt/bunkerized-nginx/gen/main.py --settings /opt/bunkerized-nginx/settings.json --templates /opt/bunkerized-nginx/confs --output /etc/nginx --variables /tmp/variables.env 2>&1)"
		if [ "$?" -ne 0 ] ; then
			log "entrypoint" "ERROR" "generator failed : $gen_ret"
			exit 1
		fi
		if [ "$gen_ret" != "" ] ; then
			log "entrypoint" "INFO" "generator output : $gen_ret"
		fi

		# call jobs
		/opt/bunkerized-nginx/entrypoint/jobs.sh
	fi
else
	log "entrypoint" "INFO" "skipping configuration process"
fi

# start crond
crond

# wait until config has been generated if we are in swarm mode
if [ "$SWARM_MODE" = "yes" ] || [ "$KUBERNETES_MODE" = "yes" ] ; then
	log "entrypoint" "INFO" "waiting until config has been generated ..."
	while [ ! -f "/etc/nginx/autoconf" ] ; do
		sleep 1
	done
fi

# stop temp config if needed
if [ -f "/tmp/nginx-temp.pid" ] ; then
	nginx -c /tmp/nginx-temp.conf -s quit
fi

# run nginx
log "entrypoint" "INFO" "running nginx ..."
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
log "entrypoint" "INFO" "bunkerized-nginx stopped"
exit 0
