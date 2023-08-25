#!/bin/bash

# Source the utils script
source /usr/share/bunkerweb/helpers/utils.sh
source /usr/share/bunkerweb/scripts/utils.sh

# Create the core.conf file if it doesn't exist 
if [ ! -f /etc/bunkerweb/core.conf ]; then
    echo "LISTEN_ADDR=127.0.0.1" > /etc/bunkerweb/core.conf
    { echo "LISTEN_PORT=1337"; echo "TOKEN=changeme"; echo "WHITELIST=127.0.0.1"; echo "CHECK_TOKEN=yes"; echo "CHECK_WHITELIST=yes"; echo "DATABASE_URI=sqlite:////var/lib/bunkerweb/db.sqlite"; echo "BUNKERWEB_INSTANCES=127.0.0.1"; } >> /etc/bunkerweb/core.conf
fi

# Function to start the Core
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting Core"
    output="$(PYTHONPATH=/usr/share/bunkerweb/deps/python python3 /usr/share/bunkerweb/core/app/core.py 2>&1)"

	if [ $? == 1 ] ; then
        # Show the output of the core
		log "ENTRYPOINT" "❌ " "$output"
		exit 1
	elif [ $? == 2 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid LISTEN_PORT, It must be an integer between 1 and 65535."
		exit 1
	elif [ $? == 3 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid MAX_WORKERS, It must be a positive integer."
		exit 1
	elif [ $? == 4 ] ; then
		log "ENTRYPOINT" "❌ " "Invalid MAX_THREADS, It must be a positive integer."
		exit 1
	fi

	source /tmp/core.tmp.env
	rm -f /tmp/core.tmp.env

    PYTHONPATH=/usr/share/bunkerweb/deps/python python3 -m gunicorn --chdir /usr/share/bunkerweb/core --bind $LISTEN_ADDR:$LISTEN_PORT --log-level $LOG_LEVEL --workers $MAX_WORKERS --threads $MAX_THREADS --config /usr/share/bunkerweb/core/gunicorn.conf.py &
    echo $! > /var/run/bunkerweb/core.pid
}

# Check the command line argument
case $1 in
    "start")
        start
        exit $?
        ;;
    "stop")
        stop "core"
        exit $?
        ;;
    "reload")
        stop "core"
        if [ $? -ne 0 ] ; then
            exit 1
        fi
        sleep 5
        start
        exit $?
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "core"
        exit 1
esac
