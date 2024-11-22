#!/bin/bash

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/ui

# Create the ui.env file if it doesn't exist
if [ ! -f /etc/bunkerweb/ui.env ]; then
    echo "ADMIN_USERNAME=" > /etc/bunkerweb/ui.env
    echo "ADMIN_PASSWORD=" >> /etc/bunkerweb/ui.env
fi

# Function to start the UI
start() {
    stop

    echo "Starting UI"
    # shellcheck disable=SC2046
    export $(cat /etc/bunkerweb/ui.env)
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --config /usr/share/bunkerweb/ui/gunicorn.conf.py --pythonpath /usr/share/bunkerweb/deps/python,/usr/share/bunkerweb/ui --bind \"127.0.0.1:7000\""
}

# Function to stop the UI
stop() {
    echo "Stopping UI service..."
    if [ -f "/var/run/bunkerweb/ui.pid" ]; then
        pid="$(cat /var/run/bunkerweb/ui.pid)"
        kill -s TERM "$pid"
    else
        echo "UI service is not running or the pid file doesn't exist."
    fi
}

# Function to reload the UI
reload() {
    stop
    sleep 5
    start
}

# Check the command line argument
case $1 in
    "start")
        start
        ;;
    "stop")
        stop
        ;;
    "reload")
        reload
        ;;
    *)
        echo "Usage: $0 {start|stop|reload}"
        exit 1
        ;;
esac
