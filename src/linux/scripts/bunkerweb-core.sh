#!/bin/bash

# Source the utils script
source utils.sh

# Create the core.conf file if it doesn't exist 
if [ ! -f /etc/bunkerweb/core.conf ]; then
    echo "LISTEN_ADDR=127.0.0.1" > /etc/bunkerweb/core.conf
    { echo "LISTEN_PORT=1337"; echo "TOKEN=changeme"; echo "WHITELIST=127.0.0.1"; echo "CHECK_TOKEN=yes"; echo "CHECK_WHITELIST=yes"; echo "DATABASE_URI=sqlite:///var/lib/bunkerweb/db.sqlite"; echo "MQ_URI=filesystem:////var/lib/bunkerweb/mq"; echo "BUNKERWEB_INSTANCES="; } >> /etc/bunkerweb/core.conf
fi

# Function to start the Core
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting Core"
    read LISTEN_ADDR LISTEN_PORT LOG_LEVEL < <(echo $(python3 /usr/share/bunkerweb/core/core.py | jq -r '.listen_addr, .listen_port, .log_level'))
    PYTHONPATH=/usr/share/bunkerweb/deps/python python3 -m gunicorn --bind $LISTEN_ADDR:$LISTEN_PORT --log-level $LOG_LEVEL --config /usr/share/bunkerweb/core/gunicorn.conf.py &
}

# Check the command line argument
case $1 in
    "start")
        start
        ;;
    "stop")
        stop "core"
        ;;
    "reload")
        stop
        sleep 5
        start
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "core"
        exit 1
esac
