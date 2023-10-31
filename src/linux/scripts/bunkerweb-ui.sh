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
    ret=$?

    if [ $ret == 1 ] ; then
            # Show the output of the core
            log "ENTRYPOINT" "❌ " "$output"
            exit 1
    elif [ $ret == 2 ] ; then
            log "ENTRYPOINT" "❌ " "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
            exit 1
    elif [ $ret == 3 ] ; then
            log "ENTRYPOINT" "❌ " "Invalid PORT, It must be an integer between 1 and 65535."
            exit 1
    fi

    set -a # turn on automatic exporting
    source /etc/bunkerweb/ui.env
    set +a # turn off automatic exporting

    python3 -m gunicorn --chdir /usr/share/bunkerweb/ui \
        --pythonpath /usr/share/bunkerweb/deps/python/ \
        --config /usr/share/bunkerweb/ui/gunicorn.conf.py \
        --log-level "$LOG_LEVEL" \
        --forwarded-allow-ips "$REVERSE_PROXY_IPS" \
        --proxy-allow-from "$REVERSE_PROXY_IPS" \
        --user nginx \
        --group nginx \
        --bind "$LISTEN_ADDR":"$LISTEN_PORT" &
    echo $! > /var/run/bunkerweb/ui.pid
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
