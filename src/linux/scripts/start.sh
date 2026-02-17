#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

# Set the PYTHONPATH
BW_PYTHONPATH=$(get_bunkerweb_pythonpath)
export PYTHONPATH="$BW_PYTHONPATH"

NGINX_BIN=$(get_nginx_bin)
NGINX_CONF_DIR=$(get_nginx_conf_dir)
# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload|restart]"
    echo "Options:"
    echo "  start:   Create configurations and start the bunkerweb service."
    echo "  stop:    Stop the bunkerweb service."
    echo "  reload:  Reload the bunkerweb service."
    echo "  restart: Stop and then start the bunkerweb service."
}

function generate_tmp_env_content() {
    cat <<EOF
IS_LOADING=yes
USE_BUNKERNET=no
SEND_ANONYMOUS_REPORT=no
SERVER_NAME=
DNS_RESOLVERS=${DNS_RESOLVERS}
API_LISTEN_HTTP=${API_LISTEN_HTTP}
API_HTTP_PORT=${API_HTTP_PORT}
API_LISTEN_HTTPS=${API_LISTEN_HTTPS}
API_HTTPS_PORT=${API_HTTPS_PORT}
API_LISTEN_IP=${API_LISTEN_IP}
API_SERVER_NAME=${API_SERVER_NAME}
API_WHITELIST_IP=${API_WHITELIST_IP}
API_TOKEN=${API_TOKEN}
USE_REAL_IP=${USE_REAL_IP}
USE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL}
REAL_IP_FROM=${REAL_IP_FROM}
REAL_IP_HEADER=${REAL_IP_HEADER}
HTTP_PORT=${HTTP_PORT}
HTTPS_PORT=${HTTPS_PORT}
KEEP_CONFIG_ON_RESTART=${KEEP_CONFIG_ON_RESTART}
EOF
}

function write_tmp_env_file() {
    local tmp_env_path="$1"
    local tmp_env_content="$2"
    printf "%s\n" "$tmp_env_content" > "$tmp_env_path"
    chown root:nginx "$tmp_env_path"
    chmod 660 "$tmp_env_path"
}

function set_loading_state() {
    local nginx_variables_path="$1"
    if [ ! -f "$nginx_variables_path" ] ; then
        return 1
    fi

    if grep -q "^IS_LOADING=" "$nginx_variables_path" ; then
        sed -i "s/^IS_LOADING=.*/IS_LOADING=yes/" "$nginx_variables_path"
    else
        echo "IS_LOADING=yes" >> "$nginx_variables_path"
    fi

    return 0
}

# Start the bunkerweb service
function start() {

    # Set the PYTHONPATH
    export PYTHONPATH="$BW_PYTHONPATH"

    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb service ..."

    if command -v setcap >/dev/null 2>&1 && [ -x "$NGINX_BIN" ]; then
        setcap 'CAP_NET_BIND_SERVICE=+eip' "$NGINX_BIN" || true
    fi
    if [ -d "$NGINX_CONF_DIR" ]; then
        chown -R nginx:nginx "$NGINX_CONF_DIR"
    fi

    # Create dummy variables.env
    if [ ! -f /etc/bunkerweb/variables.env ]; then
        {
            echo "# remove IS_LOADING=yes when your config is ready"
            echo "IS_LOADING=yes"
            echo "SERVER_NAME="
            echo "DNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4" # Quad9, Google
            echo "HTTP_PORT=80"
            echo "HTTPS_PORT=443"
            echo "API_LISTEN_IP=127.0.0.1"
            echo "API_TOKEN="
            echo "KEEP_CONFIG_ON_RESTART=no"
        } > /etc/bunkerweb/variables.env
        chown root:nginx /etc/bunkerweb/variables.env
        chmod 660 /etc/bunkerweb/variables.env
        log "SYSTEMCTL" "ℹ️" "Created dummy variables.env file"
    fi

    # Create PID folder
    if [ ! -f /var/run/bunkerweb ] ; then
        mkdir -p /var/run/bunkerweb
        chown nginx:nginx /var/run/bunkerweb
    fi

    # Create TMP folder
    if [ ! -f /var/tmp/bunkerweb ] ; then
        mkdir -p /var/tmp/bunkerweb
        chown nginx:nginx /var/tmp/bunkerweb
        chmod 2770 /var/tmp/bunkerweb
    fi

    # Create LOG folder
    if [ ! -f /var/log/bunkerweb ] ; then
        mkdir -p /var/log/bunkerweb
        chown nginx:nginx /var/log/bunkerweb
    fi

    # Stop nginx if it's running
    stop

    # Generate temp conf for nginx
    # Default values
    declare -A defaults=(
        [DNS_RESOLVERS]="9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4" # Quad9, Google
        [API_LISTEN_HTTP]="yes"
        [API_LISTEN_HTTPS]="no"
        [API_HTTP_PORT]="5000"
        [API_HTTPS_PORT]="5443"
        [API_LISTEN_IP]="127.0.0.1"
        [API_SERVER_NAME]="bwapi"
        [API_WHITELIST_IP]="127.0.0.0/8"
        [API_TOKEN]=""
        [USE_REAL_IP]="no"
        [USE_PROXY_PROTOCOL]="no"
        [REAL_IP_FROM]="192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
        [REAL_IP_HEADER]="X-Forwarded-For"
        [HTTP_PORT]="80"
        [HTTPS_PORT]="443"
        [KEEP_CONFIG_ON_RESTART]="no"
    )

    # File containing the environment variables
    env_file="/etc/bunkerweb/variables.env"

    # Load variables safely
    if [ -f "$env_file" ]; then
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            # Trim whitespace from key
            key=$(echo "$key" | xargs)
            # Only process recognized keys
            if [[ -n "${defaults[$key]}" ]]; then
                # Set variable if defined and non-empty in the file
                [[ -n "$value" ]] && eval "${key}=\"$value\""
            fi
        done < "$env_file"
    fi

    # Assign default values for unset variables
    for key in "${!defaults[@]}"; do
        eval "value=\${${key}:-}"
        if [ -z "$value" ]; then
            eval "${key}=\"${defaults[$key]}\""
        fi
    done

    tmp_env_path="/var/tmp/bunkerweb/tmp.env"
    tmp_env_content="$(generate_tmp_env_content)"
    regenerate_temp_config=false

    tmp_env_path="/var/tmp/bunkerweb/tmp.env"

    if [[ "$KEEP_CONFIG_ON_RESTART" == "no" ]] || [[ ! -f "$tmp_env_path" ]] ; then
        regenerate_temp_config=true
    else
        log "SYSTEMCTL" "ℹ️" "Preserving current config on restart, forcing loading state to receive latest config ..."
        if ! set_loading_state "/etc/nginx/variables.env" ; then
            log "SYSTEMCTL" "⚠️" "Couldn't set IS_LOADING=yes because /etc/nginx/variables.env is missing"
        fi
    fi

    write_tmp_env_file "$tmp_env_path" "$tmp_env_content"

    if [[ "$regenerate_temp_config" == "true" ]] ; then
        if ! run_as_nginx env PYTHONPATH="$BW_PYTHONPATH" "$PYTHON_BIN" /usr/share/bunkerweb/gen/main.py \
            --variables "$tmp_env_path"; then
            log "SYSTEMCTL" "❌" "Error while generating config from $tmp_env_path"
            exit 1
        fi
    fi

    # Ensure health endpoint can report "loading" (not stale "reloading")
    if [ -f /var/tmp/bunkerweb_reloading ] ; then
        rm -f /var/tmp/bunkerweb_reloading
    fi

    # Start nginx
    log "SYSTEMCTL" "ℹ️" "Starting nginx ..."
    if [ "$(uname)" = "FreeBSD" ]; then
        "$NGINX_BIN" -e /var/log/bunkerweb/error.log
        nginx_rc=$?
    else
        run_as_nginx "$NGINX_BIN" -e /var/log/bunkerweb/error.log
        nginx_rc=$?
    fi
    if [ "$nginx_rc" -ne 0 ]; then
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

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service started ..."

    while [ -f /var/run/bunkerweb/nginx.pid ] ; do
        sleep 1
    done
}

function stop() {
    log "SYSTEMCTL" "ℹ️" "Stopping BunkerWeb service ..."

    pid_file="/var/run/bunkerweb/nginx.pid"

    if [ -f "$pid_file" ] ; then
        pid="$(cat "$pid_file" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1 ; then
            log "SYSTEMCTL" "ℹ️ " "Stopping nginx (PID $pid)..."
            # Try graceful quit first
            kill -QUIT "$pid" >/dev/null 2>&1
            # Fallback to TERM if needed later
        else
            # PID file exists but process not running
            log "SYSTEMCTL" "⚠️ " "PID file exists but nginx not running; cleaning up"
            rm -f "$pid_file"
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "nginx is not running"
    fi

    # Wait for nginx to stop based on our own PID
    count=0
    if [ -n "$pid" ] ; then
        while kill -0 "$pid" >/dev/null 2>&1 ; do
            log "SYSTEMCTL" "ℹ️ " "Waiting for nginx to stop..."
            sleep 1
            count=$((count + 1))
            if [ $count -ge 20 ] ; then
                break
            fi
        done

        if kill -0 "$pid" >/dev/null 2>&1 ; then
            # Graceful stop timed out, try TERM
            log "SYSTEMCTL" "ℹ️ " "Stopping nginx (TERM)..."
            kill -TERM "$pid" >/dev/null 2>&1 || true
            # Wait a bit more
            extra=0
            while kill -0 "$pid" >/dev/null 2>&1 ; do
                sleep 1
                extra=$((extra + 1))
                if [ $extra -ge 5 ] ; then
                    break
                fi
            done
        fi

        if kill -0 "$pid" >/dev/null 2>&1 ; then
            log "SYSTEMCTL" "❌" "Timeout while waiting nginx to stop"
            exit 1
        fi
    fi

    # Ensure PID file is removed
    [ -f "$pid_file" ] && rm -f "$pid_file"

    log "SYSTEMCTL" "ℹ️ " "nginx is stopped"

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service stopped"
}

function reload()
{
    log "SYSTEMCTL" "ℹ️" "Reloading BunkerWeb service ..."

    pid_file="/var/run/bunkerweb/nginx.pid"
    if [ -f "$pid_file" ] ; then
        pid="$(cat "$pid_file" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1 ; then
            log "SYSTEMCTL" "ℹ️" "Reloading nginx ..."
            "$NGINX_BIN" -s reload
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "SYSTEMCTL" "❌" "Error while sending reload signal to nginx"
                log "SYSTEMCTL" "ℹ️" "Reloading nginx (force) ..."
                kill -HUP "$pid" >/dev/null 2>&1
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "SYSTEMCTL" "❌" "Error while sending hup signal to nginx"
                fi
            fi
        else
            log "SYSTEMCTL" "❌" "nginx is not running"
            exit 1
        fi
    else
        log "SYSTEMCTL" "❌" "nginx is not running"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service reloaded ..."
}

function restart() {
    log "SYSTEMCTL" "ℹ️" "Restarting BunkerWeb service ..."
    stop
    sleep 2
    start
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
    reload
    ;;
    "restart")
    restart
    ;;
    *)
    echo "Invalid option!"
    echo "List of options availables:"
    display_help
esac
