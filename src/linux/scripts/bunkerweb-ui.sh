#!/bin/bash

# Enforce a restrictive default umask for all operations
umask 027

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
            echo "UI_LISTEN_ADDR=127.0.0.1"
            echo "# UI_LISTEN_PORT=7000"
            echo "UI_FORWARDED_ALLOW_IPS=127.0.0.1"
            echo "# ENABLE_HEALTHCHECK=no"
        } > /etc/bunkerweb/ui.env
        chown root:nginx /etc/bunkerweb/ui.env
        chmod 660 /etc/bunkerweb/ui.env
    fi

    # Extract environment variables with fallback
    LISTEN_ADDR=$(get_env_var "UI_LISTEN_ADDR" "")
    if [ -z "$LISTEN_ADDR" ]; then
        LISTEN_ADDR=$(get_env_var "LISTEN_ADDR" "127.0.0.1")
    fi
    export LISTEN_ADDR

    FORWARDED_ALLOW_IPS=$(get_env_var "UI_FORWARDED_ALLOW_IPS" "")
    if [ -z "$FORWARDED_ALLOW_IPS" ]; then
        FORWARDED_ALLOW_IPS=$(get_env_var "FORWARDED_ALLOW_IPS" "127.0.0.1")
    fi
    export FORWARDED_ALLOW_IPS

    export CAPTURE_OUTPUT="yes"

    # Export all variables from variables.env
    if [ -f /etc/bunkerweb/variables.env ]; then
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            # Trim whitespace from key
            key=$(echo "$key" | xargs)
            # Export the variable (value may contain spaces)
            export "$key=$value"
        done < /etc/bunkerweb/variables.env
    fi

    # Export all variables from ui.env
    # But we keep the above explicit exports to ensure defaults are properly set
    if [ -f /etc/bunkerweb/ui.env ]; then
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            # Trim whitespace from key
            key=$(echo "$key" | xargs)
            # Export the variable (value may contain spaces)
            export "$key=$value"
        done < /etc/bunkerweb/ui.env
    fi

    if [ -f "/var/run/bunkerweb/tmp-ui.pid" ]; then
        rm -f /var/run/bunkerweb/tmp-ui.pid
    fi
    if [ -f "/var/run/bunkerweb/ui.pid" ]; then
        rm -f /var/run/bunkerweb/ui.pid
    fi
    if [ -f "/var/tmp/bunkerweb/ui.error" ]; then
        rm -f /var/tmp/bunkerweb/ui.error
    fi

    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --logger-class utils.logger.TmpUiLogger --config /usr/share/bunkerweb/ui/utils/tmp-gunicorn.conf.py -D"
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --logger-class utils.logger.UiLogger --config /usr/share/bunkerweb/ui/utils/gunicorn.conf.py"
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
