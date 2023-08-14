#!/bin/bash

# Source the utils script
source utils.sh

# Create the scheduler.conf file if it doesn't exist 
if [ ! -f /etc/bunkerweb/scheduler.conf ]; then
    echo "API_ADDR=http://127.0.0.1:1337" > /etc/bunkerweb/scheduler.conf
    echo "API_TOKEN=changeme" >> /etc/bunkerweb/scheduler.conf
fi

# Function to start the Scheduler
start() {
    log "SYSTEMCTL" "ℹ️" "Starting Scheduler"
    PYTHONPATH=/usr/share/bunkerweb/deps/python python3 /usr/share/bunkerweb/scheduler/main.py &
}

# Function to reload the Scheduler
reload() {
    log "SYSTEMCTL" "ℹ️" "Reloading Scheduler service ..."

    pid_file_path="/var/run/bunkerweb/scheduler.pid"
    if [ -f "$pid_file_path" ];
    then
        var=$(cat "$pid_file_path")
        # Send signal to scheduler to reload
        log "SYSTEMCTL" "ℹ️" "Sending reload signal to scheduler ..."
        kill -SIGHUP "$var"
        result=$?
        if [ $result -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Your command exited with non-zero status $result"
            exit 1
        fi
    else
        log "SYSTEMCTL" "❌" "Scheduler is not running"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️" "Scheduler service reloaded ..."
}

# Check the command line argument
# List of differents args
case $1 in
    "start") 
        start
        ;;
    "stop") 
        stop "scheduler"
        ;;
    "reload") 
        reload
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "scheduler"
        exit 1
esac
