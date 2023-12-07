#!/bin/bash

# Source the utils script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh
# shellcheck disable=SC1091
source /usr/share/bunkerweb/scripts/utils.sh

export PYTHONPATH=/usr/share/bunkerweb/deps/python

# Create the ui.conf file if it doesn't exist
if [ ! -f /etc/bunkerweb/ui.conf ]; then
    cp /usr/share/bunkerweb/ui/ui.conf.example /etc/bunkerweb/ui.conf
fi

# Function to start the UI
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting UI"
    output="$(python3 /usr/share/bunkerweb/ui/ui.py 2>&1)"

    # shellcheck disable=SC2181
	if ! [ $? -eq 0 ] ; then
		# Show the output of the ui
		echo "$output"
		exit 1
	fi

    set -a # turn on automatic exporting
    source /etc/bunkerweb/ui.env
    set +a # turn off automatic exporting

    python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --config /usr/share/bunkerweb/ui/gunicorn.conf.py --access-logfile /var/log/bunkerweb/ui-access.log &
    while [ ! -f /var/run/bunkerweb/ui.pid ]; do
        sleep 1
    done
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
