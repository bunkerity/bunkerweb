#!/bin/bash

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/ui

# Create the ui.env file if it doesn't exist
if [ ! -f /etc/bunkerweb/ui.env ]; then
    {
        echo "# OVERRIDE_ADMIN_CREDS=no"
        echo "ADMIN_USERNAME="
        echo "ADMIN_PASSWORD="
        echo "# FLASK_SECRET=changeme"
        echo "# TOTP_SECRETS=changeme"
        echo "LISTEN_ADDR=127.0.0.1"
        echo "# LISTEN_PORT=7000"
        echo "FORWARDED_ALLOW_IPS=127.0.0.1"
    } > /etc/bunkerweb/ui.env
    chown root:nginx /etc/bunkerweb/ui.env
    chmod 660 /etc/bunkerweb/ui.env
fi

# Function to start the UI
start() {
    stop

    echo "Starting UI"
    export LISTEN_ADDR="127.0.0.1"
    export FORWARDED_ALLOW_IPS="127.0.0.1"
    export CAPTURE_OUTPUT="yes"
    # shellcheck disable=SC2046
    export $(cat /etc/bunkerweb/ui.env)
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --logger-class utils.logger.TmpUiLogger --config utils/tmp-gunicorn.conf.py"
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m gunicorn --chdir /usr/share/bunkerweb/ui --logger-class utils.logger.UiLogger --config utils/gunicorn.conf.py"
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
