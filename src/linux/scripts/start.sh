#!/bin/bash

# Source the utils script
source /usr/share/bunkerweb/helpers/utils.sh
source /usr/share/bunkerweb/scripts/utils.sh

# Start the bunkerweb service
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb service ..."

    echo "nginx ALL=(ALL) NOPASSWD: /usr/sbin/nginx" > /etc/sudoers.d/bunkerweb
    chown -R nginx:nginx /etc/nginx

    # Create dummy variables.env
    if [ ! -f /etc/bunkerweb/variables.env ]; then
        sudo -E -u nginx -g nginx /bin/bash -c "echo -ne '# remove IS_LOADING=yes when your config is ready\nIS_LOADING=yes\nDNS_RESOLVERS=8.8.8.8 8.8.4.4\nHTTP_PORT=80\nHTTPS_PORT=443\nAPI_LISTEN_IP=127.0.0.1\nSERVER_NAME=\n' > /etc/bunkerweb/variables.env"
        log "SYSTEMCTL" "ℹ️" "Created dummy variables.env file"
    fi

    # Stop nginx if it's running
    stop

    # TODO change this to the new format

    # Generate temp conf for jobs and start nginx
    HTTP_PORT="$(grep "^HTTP_PORT=" /etc/bunkerweb/variables.env | cut -d '=' -f 2)"
    if [ "$HTTP_PORT" = "" ] ; then
        HTTP_PORT="8080"
    fi

    HTTPS_PORT="$(grep "^HTTPS_PORT=" /etc/bunkerweb/variables.env | cut -d '=' -f 2)"
    if [ "$HTTPS_PORT" = "" ] ; then
        HTTPS_PORT="8443"
    fi

    sudo -E -u nginx -g nginx /bin/bash -c "echo -ne 'IS_LOADING=yes\nUSE_BUNKERNET=no\nHTTP_PORT=${HTTP_PORT}\nHTTPS_PORT=${HTTPS_PORT}\nAPI_LISTEN_IP=127.0.0.1\nSERVER_NAME=\n' > /var/tmp/bunkerweb/tmp.env"
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=/usr/share/bunkerweb/deps/python/ /usr/share/bunkerweb/gen/main.py --variables /var/tmp/bunkerweb/tmp.env --no-linux-reload"

    if [ $? -ne 0 ] ; then
        log "SYSTEMCTL" "❌" "Error while generating config from /var/tmp/bunkerweb/tmp.env"
        exit 1
    fi

    # Start nginx
    log "SYSTEMCTL" "ℹ️" "Starting temp nginx ..."
    nginx -e /var/log/bunkerweb/error.log
    if [ $? -ne 0 ] ; then
        log "SYSTEMCTL" "❌" "Error while executing temp nginx"
        exit 1
    fi
    count=0

    while [ $count -lt 10 ] ; do
        check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
        if [ $? -eq 0 ] && [ "$check" = "ok" ] ; then
            break
        fi
        count=$((count + 1))
        sleep 1
        log "SYSTEMCTL" "ℹ️" "Waiting for nginx to start ..."
    done

    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "nginx is not started"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️" "nginx started ..."
}

function stop() {
    pgrep nginx > /dev/null 2>&1
    if [ $? -eq 0 ] ; then
        log "SYSTEMCTL" "ℹ️ " "Stopping nginx..."
        nginx -s stop
        if [ $? -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Error while sending stop signal to nginx"
            log "SYSTEMCTL" "ℹ️ " "Stopping nginx (force)..."
            kill -TERM "$(cat /var/run/bunkerweb/nginx.pid)"
            if [ $? -ne 0 ] ; then
                log "SYSTEMCTL" "❌" "Error while sending term signal to nginx"
            fi
        fi
    fi

    count=0
    while [ true ] ; do
        pgrep nginx > /dev/null 2>&1
        if [ $? -ne 0 ] ; then
            break
        fi
        log "SYSTEMCTL" "ℹ️ " "Waiting for nginx to stop..."
        sleep 1
        count=$((count + 1))
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

# List of differents args
case $1 in
    "start") 
        start
        ;;
    "stop") 
        stop
        ;;
    "reload") 
        stop
        sleep 5
        start
        ;;
    *)
        echo "Invalid option!"
        echo "List of options availables:"
        display_help "bunkerweb"
        exit 1
esac
