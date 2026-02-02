#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/ui

# Helper function to extract variables with fallback
function get_env_var() {
    local var_name=$1
    local default_value=$2
    local value

    # First try ui.env
    value=$(grep "^${var_name}=" /etc/bunkerweb/ui.env 2>/dev/null | cut -d '=' -f 2)

    # If not found, try variables.env
    if [ -z "$value" ] && [ -f /etc/bunkerweb/variables.env ]; then
        value=$(grep "^${var_name}=" /etc/bunkerweb/variables.env 2>/dev/null | cut -d '=' -f 2)
    fi

    # Return default if still not found
    if [ -z "$value" ]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

# Function to start the UI
start() {
    stop

    echo "Starting UI"

    # Create the ui.env file if it doesn't exist
    if [ ! -f /etc/bunkerweb/ui.env ]; then
        {
            echo "# OVERRIDE_ADMIN_CREDS=no"
            echo "ADMIN_USERNAME="
            echo "ADMIN_PASSWORD="
            echo "# FLASK_SECRET=changeme"
            echo "# TOTP_ENCRYPTION_KEYS=changeme"
            echo "LISTEN_ADDR=127.0.0.1"
            echo "# LISTEN_PORT=7000"
            echo "FORWARDED_ALLOW_IPS=127.0.0.1,::1"
            echo "PROXY_ALLOW_IPS=127.0.0.1,::1"
            echo "# ENABLE_HEALTHCHECK=no"
            echo "LOG_LEVEL=info"
            echo "LOG_TYPES=file"
            echo "# LOG_FILE_PATH=/var/log/bunkerweb/ui.log"
        } > /etc/bunkerweb/ui.env
        chown root:nginx /etc/bunkerweb/ui.env
        chmod 660 /etc/bunkerweb/ui.env
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

    # Extract environment variables with fallback
    LISTEN_ADDR=$(get_env_var "UI_LISTEN_ADDR" "")
    if [ -z "$LISTEN_ADDR" ]; then
        LISTEN_ADDR=$(get_env_var "LISTEN_ADDR" "127.0.0.1")
    fi
    export LISTEN_ADDR

    LISTEN_PORT=$(get_env_var "UI_LISTEN_PORT" "")
    if [ -z "$LISTEN_PORT" ]; then
        LISTEN_PORT=$(get_env_var "LISTEN_PORT" "7000")
    fi
    export LISTEN_PORT

    FORWARDED_ALLOW_IPS=$(get_env_var "UI_FORWARDED_ALLOW_IPS" "")
    if [ -z "$FORWARDED_ALLOW_IPS" ]; then
        FORWARDED_ALLOW_IPS=$(get_env_var "FORWARDED_ALLOW_IPS" "127.0.0.1,::1")
    fi
    export FORWARDED_ALLOW_IPS

    PROXY_ALLOW_IPS=$(get_env_var "UI_PROXY_ALLOW_IPS" "")
    if [ -z "$PROXY_ALLOW_IPS" ]; then
        PROXY_ALLOW_IPS=$(get_env_var "PROXY_ALLOW_IPS" "$FORWARDED_ALLOW_IPS")
    fi
    export PROXY_ALLOW_IPS

    LOG_TYPES=$(get_env_var "UI_LOG_TYPES" "")
    if [ -z "$LOG_TYPES" ]; then
        LOG_TYPES=$(get_env_var "LOG_TYPES" "file")
    fi
    export LOG_TYPES

    LOG_FILE_PATH=$(get_env_var "UI_LOG_FILE_PATH" "")
    if [ -z "$LOG_FILE_PATH" ]; then
        LOG_FILE_PATH=$(get_env_var "LOG_FILE_PATH" "/var/log/bunkerweb/ui.log")
    fi
    export LOG_FILE_PATH

    LOG_SYSLOG_TAG=$(get_env_var "UI_LOG_SYSLOG_TAG" "")
    if [ -z "$LOG_SYSLOG_TAG" ]; then
        LOG_SYSLOG_TAG=$(get_env_var "LOG_SYSLOG_TAG" "bw-ui")
    fi
    export LOG_SYSLOG_TAG

    export CAPTURE_OUTPUT="yes"

    # But we keep the above explicit exports to ensure defaults are properly set
    export_env_file /etc/bunkerweb/variables.env
    export_env_file /etc/bunkerweb/ui.env

    if [ -f "/var/run/bunkerweb/tmp-ui.pid" ]; then
        rm -f /var/run/bunkerweb/tmp-ui.pid
    fi
    if [ -f "/var/run/bunkerweb/ui.pid" ]; then
        rm -f /var/run/bunkerweb/ui.pid
    fi
    if [ -f "/var/tmp/bunkerweb/ui.error" ]; then
        rm -f /var/tmp/bunkerweb/ui.error
    fi

    if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m gunicorn \
        --chdir /usr/share/bunkerweb/ui \
        --logger-class utils.logger.TmpUiLogger \
        --config /usr/share/bunkerweb/ui/utils/tmp-gunicorn.conf.py -D; then
        echo "Failed to start temporary UI service (nginx user execution error)"
        exit 1
    fi

    if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m gunicorn \
        --chdir /usr/share/bunkerweb/ui \
        --logger-class utils.logger.UiLogger \
        --config /usr/share/bunkerweb/ui/utils/gunicorn.conf.py; then
        echo "Failed to start UI service (nginx user execution error)"
        exit 1
    fi
}

# Function to stop the UI
stop() {
    echo "Stopping UI service..."

    if [ -f "/var/run/bunkerweb/tmp-ui.pid" ]; then
        pid="$(cat /var/run/bunkerweb/tmp-ui.pid)"
        kill -s TERM "$pid"
    else
        echo "Temporary UI service is not running or the pid file doesn't exist."
    fi

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

# Function to restart the UI
restart() {
    echo "Restarting UI service..."
    stop
    sleep 2
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
    "restart")
        restart
        ;;
    *)
        echo "Usage: $0 {start|stop|reload|restart}"
        exit 1
        ;;
esac
