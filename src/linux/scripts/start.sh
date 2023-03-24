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

function stop_nginx() {
    pgrep nginx
    if [ $? -eq 0 ] ; then
        log "SYSTEMCTL" "ℹ️ " "Stopping nginx..."
        nginx -s stop
        if [ $? -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Error while sending stop signal to nginx"
        fi
    fi
    count=0
    while [ 1 ] ; do
        pgrep nginx
        if [ $? -ne 0 ] ; then
            break
        fi
        log "SYSTEMCTL" "ℹ️ " "Waiting for nginx to stop..."
        sleep 1
        count=$(($count + 1))
        if [ $count -ge 20 ] ; then
            break
        fi
    done
    if [ $count -ge 20 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting nginx to stop"
        exit 1
    fi
    log "SYSTEMCTL" "ℹ️ " "nginx is stopped"
}

function stop_scheduler() {
    if [ -f "/var/tmp/bunkerweb/scheduler.pid" ] ; then
        scheduler_pid=$(cat "/var/tmp/bunkerweb/scheduler.pid")
        log "SYSTEMCTL" "ℹ️ " "Stopping scheduler..."
        kill -SIGINT "$scheduler_pid"
        if [ $? -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Error while sending stop signal to scheduler"
            exit 1
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "Scheduler already stopped"
        return 0
    fi
    count=0
    while [ -f "/var/tmp/bunkerweb/scheduler.pid" ] ; do
        sleep 1
        count=$(($count + 1))
        if [ $count -ge 10 ] ; then
            break
        fi
    done
    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting scheduler to stop"
        exit 1
    fi
    log "SYSTEMCTL" "ℹ️ " "Scheduler is stopped"
}

# Start the bunkerweb service
function start() {

    # Set the PYTHONPATH
    export PYTHONPATH=/usr/share/bunkerweb/deps/python

    log "ENTRYPOINT" "ℹ️" "Starting BunkerWeb service ..."

    # Setup and check /data folder
    /usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

    # Stop scheduler if it's running
    stop_scheduler

    # Stop nginx if it's running
    stop_nginx

    # Generate temp conf for jobs and start nginx
    if [ ! -f /var/tmp/bunkerweb/tmp.env ] ; then
        echo -ne "IS_LOADING=yes\nHTTP_PORT=80\nHTTPS_PORT=443\nAPI_LISTEN_IP=127.0.0.1\nSERVER_NAME=\n" > /var/tmp/bunkerweb/tmp.env
    fi
    /usr/share/bunkerweb/gen/main.py --variables /var/tmp/bunkerweb/tmp.env --no-linux-reload
    if [ $? -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Error while generating config from /var/tmp/bunkerweb/tmp.env"
        exit 1
    fi

    # Start nginx
    log "ENTRYPOINT" "ℹ️" "Starting nginx ..."
    nginx
    if [ $? -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Error while executing nginx"
        exit 1
    fi
    count=0
    while [ $count -lt 10 ] ; do
        check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
        if [ $? -eq 0 ] && [ "$check" = "ok" ] ; then
            break
        fi
        count=$(($count + 1))
        sleep 1
        log "ENTRYPOINT" "ℹ️" "Waiting for nginx to start ..."
    done
    if [ $count -ge 10 ] ; then
        log "ENTRYPOINT" "❌" "nginx is not started"
        exit 1
    fi
    log "ENTRYPOINT" "ℹ️" "nginx started ..."

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
    if [ $? -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "save_config failed"
        exit 1
    fi

    # Execute scheduler
    log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
    /usr/share/bunkerweb/scheduler/main.py --variables /etc/bunkerweb/variables.env
    if [ "$?" -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Scheduler failed"
        exit 1
    fi

    log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
}

function stop() {
    log "ENTRYPOINT" "ℹ️" "Stopping BunkerWeb service ..."

    stop_nginx
    stop_scheduler

    log "ENTRYPOINT" "ℹ️" "BunkerWeb service stopped"
}

function reload()
{

    log "ENTRYPOINT" "ℹ️" "Reloading BunkerWeb service ..."

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

    log "ENTRYPOINT" "ℹ️" "BunkerWeb service reloaded ..."
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