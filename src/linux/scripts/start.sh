#!/bin/bash

# Source the utils script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh
# shellcheck disable=SC1091
source /usr/share/bunkerweb/scripts/utils.sh

export PYTHONPATH=/usr/share/bunkerweb/deps/python/

function get_var() {
    rerunuserlt="$(grep "^$1=" /etc/bunkerweb/variables.env | cut -d '=' -f 2)"
    if [ "$rerunuserlt" = "" ] ; then
        rerunuserlt="$(echo "$@" | cut -d ' ' -f 2-)"
    fi
    echo "$rerunuserlt"
}

# Start the bunkerweb service
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb service ..."

    setcap 'CAP_NET_BIND_SERVICE=+eip' /usr/sbin/nginx
    chown -R nginx:nginx /etc/nginx

    # Create dummy variables.env
    if [ ! -f /etc/bunkerweb/variables.env ]; then
        runuser -p -g nginx -s /bin/bash -c "echo -ne '# remove IS_LOADING=yes when your config is ready\nIS_LOADING=yes\nUSE_BUNKERNET=no\nDNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4\nHTTP_PORT=80\nHTTPS_PORT=443\nAPI_LISTEN_IP=127.0.0.1\nSERVER_NAME=\n' > /etc/bunkerweb/variables.env" nginx
        log "SYSTEMCTL" "ℹ️" "Created dummy variables.env file"
    fi

    # Stop nginx if it's running
    stop

    # Generate temp conf for jobs and start nginx
    DNS_RESOLVERS="$(get_var "DNS_RESOLVERS" "9.9.9.9 8.8.8.8 8.8.4.4")"
    API_LISTEN_IP="$(get_var "API_LISTEN_IP" "127.0.0.1")"
    API_HTTP_PORT="$(get_var "API_HTTP_PORT" "5000")"
    API_SERVER_NAME="$(get_var "API_SERVER_NAME" "bwapi")"
    API_WHITELIST_IP="$(get_var "API_WHITELIST_IP" "127.0.0.0/8")"
    USE_REAL_IP="$(get_var "USE_REAL_IP" "no")"
    USE_PROXY_PROTOCOL="$(get_var "USE_PROXY_PROTOCOL" "no")"
    REAL_IP_FROM="$(get_var "REAL_IP_FROM" "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8")"
    REAL_IP_HEADER="$(get_var "REAL_IP_HEADER" "X-Forwarded-For")"
    HTTP_PORT="$(get_var "HTTP_PORT" "80")"
    HTTPS_PORT="$(get_var "HTTPS_PORT" "443")"
    runuser -p -g nginx -s /bin/bash -c "echo -ne 'IS_LOADING=yes\nUSE_BUNKERNET=no\nSERVER_NAME=\nDNS_RESOLVERS=${DNS_RESOLVERS}\nAPI_HTTP_PORT=${API_HTTP_PORT}\nAPI_LISTEN_IP=${API_LISTEN_IP}\nAPI_SERVER_NAME=${API_SERVER_NAME}\nAPI_WHITELIST_IP=${API_WHITELIST_IP}\nUSE_REAL_IP=${USE_REAL_IP}\nUSE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL}\nREAL_IP_FROM=${REAL_IP_FROM}\nREAL_IP_HEADER=${REAL_IP_HEADER}\nHTTP_PORT=${HTTP_PORT}\nHTTPS_PORT=${HTTPS_PORT}\n' > /var/tmp/bunkerweb/tmp.env" nginx
    runuser -p -g nginx -s /bin/bash -c "/usr/share/bunkerweb/gen/main.py --variables /var/tmp/bunkerweb/tmp.env --no-linux-reload" nginx
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "SYSTEMCTL" "❌" "Error while generating config from /var/tmp/bunkerweb/tmp.env"
        exit 1
    fi

    if [ ! -f /var/run/bunkerweb ] ; then
        mkdir -p /var/run/bunkerweb
        chown root:nginx /var/run/bunkerweb
    fi

    # Start nginx
    log "SYSTEMCTL" "ℹ️" "Starting nginx ..."
    runuser -p -g nginx -s /bin/bash -c "/usr/sbin/nginx -e /var/log/bunkerweb/error.log" nginx
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "SYSTEMCTL" "❌" "Error while executing temp nginx"
        exit 1
    fi
    count=0

    while [ $count -lt 10 ] ; do
        check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
        # shellcheck disable=SC2181
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
    # shellcheck disable=SC2181
    if [ $? -eq 0 ] ; then
        log "SYSTEMCTL" "ℹ️ " "Stopping nginx..."
        nginx -s stop
        # shellcheck disable=SC2181
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
    while true ; do
        pgrep nginx > /dev/null 2>&1
        # shellcheck disable=SC2181
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

# List of different args
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
