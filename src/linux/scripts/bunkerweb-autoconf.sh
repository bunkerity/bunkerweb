#!/bin/bash

# Source the utils script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh
# shellcheck disable=SC1091
source /usr/share/bunkerweb/scripts/utils.sh

# Create the ui.conf file if it doesn't exist
if [ ! -f /etc/bunkerweb/autoconf.conf ]; then
    cp /usr/share/bunkerweb/autoconf/autoconf.conf.example /etc/bunkerweb/autoconf.conf
fi

# Function to start the UI
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting Autoconf"
    python3 /usr/share/bunkerweb/autoconf/main.py &
}

# Check the command line argument
case $1 in
    "start")
        start
        ;;
    "stop")
        stop "autoconf"
        ;;
    "reload")
        stop
        sleep 5
        start
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "autoconf"
        exit 1
esac
