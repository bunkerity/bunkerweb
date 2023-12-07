#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Display usage information
function display_help() {
    service=$1

    if [ -z "$service" ]; then
        echo "No service specified."
        exit 1
    fi

    echo "Usage: $(basename "$0") [start|stop|reload]"
    echo "Options:"
    echo "  start:   Create configurations and run necessary jobs for the $service service."
    echo "  stop:    Stop the $service service."
    echo "  reload:  Reload the $service service."
}

# Function to stop the service
function stop() {
    service=$1

    if [ -z "$service" ]; then
        echo "No service specified."
        exit 1
    fi

    service_name=$(echo "$service" | tr '[:lower:]' '[:upper:]')

    if [ -f "/var/run/bunkerweb/$service.pid" ] ; then
        service_pid=$(cat "/var/run/bunkerweb/$service.pid")
        if [ -n "$service_pid" ] ; then
            log "SYSTEMCTL" "ℹ️ " "Stopping $service..."
            kill -SIGINT "$service_pid"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "SYSTEMCTL" "❌" "Error while sending stop signal to $service"
                exit 1
            fi
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "$service_name already stopped"
        return 0
    fi

    count=0
    while [ -f "/var/run/bunkerweb/$service.pid" ] ; do
        sleep 1
        count=$((count + 1))
        if [ $count -ge 10 ] ; then
            break
        fi
    done

    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting $service to stop"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️ " "$service_name is stopped"
}

export -f display_help
export -f stop
