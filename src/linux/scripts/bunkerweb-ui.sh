#!/bin/bash

# Source the utils script
source /usr/share/bunkerweb/helpers/utils.sh
source /usr/share/bunkerweb/scripts/utils.sh

# Create the ui.conf file if it doesn't exist 
if [ ! -f /etc/bunkerweb/ui.conf ]; then
    echo "API_ADDR=http://127.0.0.1:1337" > /etc/bunkerweb/ui.conf
    { echo "API_TOKEN=changeme"; echo "ADMIN_USERNAME=admin"; echo "ADMIN_PASSWORD=changeme"; } >> /etc/bunkerweb/ui.conf
fi

# Function to start the UI
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting UI"
    # python3 -m gunicorn --config /usr/share/bunkerweb/ui/gunicorn.conf.py --user nginx --group nginx --bind 127.0.0.1:7000 & # TODO change this
}

# Check the command line argument
case $1 in
    "start")
        start
        ;;
    "stop")
        stop "ui"
        ;;
    "reload")
        stop
        sleep 5
        start
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "ui"
        exit 1
esac
