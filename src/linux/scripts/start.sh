#!/bin/bash

# Source the utils helper script
source /usr/share/bunkerweb/helpers/utils.sh

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python/

# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload]"
    echo "Options:"
    echo "  start:   Create configurations and run necessary jobs for the bunkerweb service."
    echo "  stop:    Stop the bunkerweb service."
    echo "  reload:  Reload the bunkerweb service."
}

# Start the bunkerweb service
function start() {
    # Set the PYTHONPATH
    export PYTHONPATH=/usr/share/bunkerweb/deps/python
    
    # Get the pid of nginx and put it in a file
    log "ENTRYPOINT" "ℹ️" "Getting nginx pid ..."
    nginx_pid=$(pgrep -x "nginx")
    echo $nginx_pid > /var/tmp/bunkerweb/nginx.pid

    # Check if scheduler pid file exist and remove it if so
    # if [ -f /var/tmp/bunkerweb/scheduler.pid ] ; then
    #     rm -f /var/tmp/bunkerweb/scheduler.pid
    # fi

    # Setup and check /data folder
    /usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

    # Create dummy variables.env
    if [ ! -f /etc/bunkerweb/variables.env ]; then
        echo -ne "# remove IS_LOADING=yes when your config is ready\nIS_LOADING=yes\nHTTP_PORT=80\nHTTPS_PORT=443\nAPI_LISTEN_IP=127.0.0.1\nSERVER_NAME=\n" > /etc/bunkerweb/variables.env
    fi

    # Update database
    if [ ! -f /var/lib/bunkerweb/db.sqlite3 ]; then
        /usr/share/bunkerweb/gen/save_config.py --variables /etc/bunkerweb/variables.env --init
    else
        /usr/share/bunkerweb/gen/save_config.py --variables /etc/bunkerweb/variables.env
    fi
    if [ "$?" -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Scheduler generator failed"
        exit 1
    fi

    # Execute jobs
    log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
    /usr/share/bunkerweb/scheduler/main.py --variables /etc/bunkerweb/variables.env
    if [ "$?" -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Scheduler failed"
        exit 1
    fi

    log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
    exit 0
}

function stop() {
    ret=0

    log "ENTRYPOINT" "ℹ️" "Stopping BunkerWeb service ..."

    # Check if pid file exist and remove it if so
    pid_file_path="/var/tmp/bunkerweb/scheduler.pid"
    if [ -f "$pid_file_path" ]; then
        scheduler_pid=$(cat "$pid_file_path")
        log "ENTRYPOINT" "ℹ️" "Sending stop signal to scheduler with pid: $scheduler_pid"
        kill -SIGINT $scheduler_pid
        if [ "$?" -ne 0 ]; then
            log "ENTRYPOINT" "❌" "Failed to stop scheduler process with pid: $scheduler_pid"
            exit 1
        fi
    else
        log "ENTRYPOINT" "❌" "Scheduler is not running"
        ret=1
    fi

    # Check if nginx is running and if so, stop it
    service="nginx"
    if pgrep -x "$service" > /dev/null; then
        log "ENTRYPOINT" "ℹ️" "Stopping $service service"
        nginx -s quit
        if [ "$?" -ne 0 ]; then
            log "ENTRYPOINT" "❌" "Failed to stop $service service"
            exit 1
        fi
    else
        log "ENTRYPOINT" "❌" "$service is not running"
        ret=1
    fi

    exit $ret
}

function reload()
{
    log "ENTRYPOINT" "ℹ️" "Reloading BunkerWeb service ..."
    # Send signal to scheduler to reload
    PID_FILE_PATH="/var/tmp/bunkerweb/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$(cat "$PID_FILE_PATH")
        # Send signal to scheduler to reload
        log "ENTRYPOINT" "ℹ️" "Sending reload signal to scheduler ..."
        kill -SIGHUP $var
        result=$?
        if [ $result -ne 0 ] ; then
            log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
            exit 1
        fi
    else
        log "ENTRYPOINT" "❌" "Scheduler is not running"
        exit 1
    fi
}

# List of differents args
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
    echo "Invalid option!"
    echo "List of options availables:"
    display_help
esac