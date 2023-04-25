#!/bin/bash

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python

# Create the ui.env file if it doesn't exist 
if [ ! -f /etc/bunkerweb/ui.env ]; then
    echo "ADMIN_USERNAME=admin" > /etc/bunkerweb/ui.env
    echo "ADMIN_PASSWORD=changeme" >> /etc/bunkerweb/ui.env
    echo "ABSOLUTE_URI=http://mydomain.ext/mypath/" >> /etc/bunkerweb/ui.env
fi

# Function to start the UI
start() {
    echo "Starting UI"
    if [ ! -f /var/tmp/bunkerweb/ui.pid ]; then
        touch /var/tmp/bunkerweb/ui.pid
    fi
    source /etc/bunkerweb/ui.env
    export $(cat /etc/bunkerweb/ui.env)
    python3 -m gunicorn --graceful-timeout=0 --bind=127.0.0.1:7000 --chdir /usr/share/bunkerweb/ui/ --workers=1 --threads=4 main:app &
    echo $! > /var/tmp/bunkerweb/ui.pid
}

# Function to stop the UI
stop() {
    echo "Stopping UI service..."
    if [ -f "/var/tmp/bunkerweb/ui.pid" ]; then
        pid=$(cat /var/tmp/bunkerweb/ui.pid)
        kill -s TERM $pid
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