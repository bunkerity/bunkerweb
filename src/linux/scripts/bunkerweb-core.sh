#!/bin/bash

# Source the utils script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh
# shellcheck disable=SC1091
source /usr/share/bunkerweb/scripts/utils.sh

export PYTHONPATH=/usr/share/bunkerweb/deps/python

# Create the core.conf file if it doesn't exist
if [ ! -f /etc/bunkerweb/core.conf ]; then
    cp /usr/share/bunkerweb/core/core.conf.example /etc/bunkerweb/core.conf
fi

# Function to start the Core
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting Core"
    output="$(python3 /usr/share/bunkerweb/core/app/core.py 2>&1)"

    # shellcheck disable=SC2181
	if ! [ $? -eq 0 ] ; then
		# Show the output of the core
		echo "$output"
		exit 1
	fi

    set -a # turn on automatic exporting
	# shellcheck disable=SC1091
	source /tmp/core.tmp.env
	set +a # turn off automatic exporting
	rm -f /tmp/core.tmp.env

    python3 -m gunicorn --chdir /usr/share/bunkerweb/core --config /usr/share/bunkerweb/core/gunicorn.conf.py --access-logfile /var/log/bunkerweb/core-access.log &
    while [ ! -f /var/run/bunkerweb/core.pid ]; do
        sleep 1
    done
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
        # shellcheck disable=SC2181
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
