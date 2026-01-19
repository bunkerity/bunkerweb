#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db

# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload|restart]"
    echo "Options:"
    echo "  start:   Create configurations and run necessary jobs for the bunkerweb service."
    echo "  stop:    Stop the bunkerweb scheduler service."
    echo "  reload:  Reload the bunkerweb scheduler service."
    echo "  restart: Stop and then start the bunkerweb scheduler service."
}

# Start the bunkerweb service
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb Scheduler service ..."

    chown -R nginx:nginx /etc/nginx

    # Check if the scheduler is already running
    stop

    # Create the scheduler.env file if it doesn't exist
    if [ ! -f /etc/bunkerweb/scheduler.env ]; then
        {
            echo "LOG_LEVEL=info"
            echo "LOG_TYPES=file"
            echo "# LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log"
            echo "# in seconds"
            echo "HEALTHCHECK_INTERVAL=30"
            echo ""
            echo "# in seconds (the minimum is calculated by the formula and whichever is greater: RELOAD_MIN_TIMEOUT or count(SERVERS) * 2))"
            echo "RELOAD_MIN_TIMEOUT=5"
        } > /etc/bunkerweb/scheduler.env
        chown root:nginx /etc/bunkerweb/scheduler.env
        chmod 660 /etc/bunkerweb/scheduler.env
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

    # Export variables from env files (scheduler overrides variables.env)
    export_env_file /etc/bunkerweb/variables.env
    export_env_file /etc/bunkerweb/scheduler.env

    : "${LOG_LEVEL:=INFO}"
    : "${CUSTOM_LOG_LEVEL:=$LOG_LEVEL}"

    if [ -n "${SCHEDULER_LOG_TYPES:-}" ]; then
        LOG_TYPES="$SCHEDULER_LOG_TYPES"
    else
        : "${LOG_TYPES:=file}"
    fi

    if [ -n "${SCHEDULER_LOG_FILE_PATH:-}" ]; then
        LOG_FILE_PATH="$SCHEDULER_LOG_FILE_PATH"
    else
        : "${LOG_FILE_PATH:=/var/log/bunkerweb/scheduler.log}"
    fi

    if [ -n "${SCHEDULER_LOG_SYSLOG_TAG:-}" ]; then
        LOG_SYSLOG_TAG="$SCHEDULER_LOG_SYSLOG_TAG"
    else
        : "${LOG_SYSLOG_TAG:=bw-scheduler}"
    fi

    : "${LOG_SYSLOG_ADDRESS:=}"
    : "${HEALTHCHECK_INTERVAL:=30}"
    : "${RELOAD_MIN_TIMEOUT:=5}"
    : "${DISABLE_CONFIGURATION_TESTING:=no}"
    : "${IGNORE_FAIL_SENDING_CONFIG:=no}"
    : "${IGNORE_REGEX_CHECK:=no}"
    : "${DATABASE_URI:=sqlite:////var/lib/bunkerweb/db.sqlite3}"
    : "${DATABASE_RETRY_TIMEOUT:=60}"
    : "${DATABASE_LOG_LEVEL:=WARNING}"

    export LOG_LEVEL CUSTOM_LOG_LEVEL LOG_TYPES LOG_FILE_PATH LOG_SYSLOG_TAG LOG_SYSLOG_ADDRESS
    export HEALTHCHECK_INTERVAL RELOAD_MIN_TIMEOUT DISABLE_CONFIGURATION_TESTING IGNORE_FAIL_SENDING_CONFIG IGNORE_REGEX_CHECK
    export DATABASE_URI DATABASE_RETRY_TIMEOUT DATABASE_LOG_LEVEL

    # Database migration section
    log "SYSTEMCTL" "ℹ️" "Checking database configuration..."
    cd /usr/share/bunkerweb/db/alembic || {
        log "SYSTEMCTL" "❌" "Failed to access database migration directory"
        exit 1
    }

    # Extract and validate database type
    DATABASE=$(echo "$DATABASE_URI" | awk -F: '{print $1}' | awk -F+ '{print $1}')

    # Check current version and stamp
    log "SYSTEMCTL" "ℹ️" "Checking database version..."
    installed_version=$(cat /usr/share/bunkerweb/VERSION)
    # Create temporary Python script
    cat > /tmp/version_check.py << EOL
#!/usr/bin/env python3
from os import getenv
import sqlalchemy as sa
from traceback import format_exc

from Database import Database
from logger import getLogger

LOGGER = getLogger("SCHEDULER.SYSTEMD")

db = None
try:
    db = Database(LOGGER)
    with db.sql_engine.connect() as conn:
        # Check if the table exists first
        inspector = sa.inspect(db.sql_engine)
        if "bw_metadata" in inspector.get_table_names():
            result = conn.execute(sa.text("SELECT version FROM bw_metadata WHERE id = 1"))
            print(next(result)[0])
        else:
            # Table doesn't exist, use installed version
            print("${installed_version}")
except BaseException as e:
    with open("/var/tmp/bunkerweb/database_error", "w") as file:
        file.write(format_exc())
    print("none")

if db:
    with open("/var/tmp/bunkerweb/database_uri", "w") as file:
        file.write(db.database_uri)
EOL
    # Ensure the temporary script is readable by nginx under UMask=027
    chown root:nginx /tmp/version_check.py
    chmod 640 /tmp/version_check.py

    current_version=$(run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" /tmp/version_check.py)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
        log "SYSTEMCTL" "❌" "Failed to retrieve database version (nginx user execution error)"
        rm -f /tmp/version_check.py
        exit 1
    fi
    rm -f /tmp/version_check.py

    if [ -f /var/tmp/bunkerweb/database_error ]; then
        log "SYSTEMCTL" "❌" "Failed to retrieve database version: $(cat /var/tmp/bunkerweb/database_error)"
        rm -f /var/tmp/bunkerweb/database_error
        exit 1
    elif [ ! -f /var/tmp/bunkerweb/database_uri ]; then
        log "SYSTEMCTL" "❌" "Failed to retrieve database URI"
        exit 1
    fi

    DATABASE_URI=$(cat /var/tmp/bunkerweb/database_uri)
    export DATABASE_URI
    rm -f /var/tmp/bunkerweb/database_uri

    # Update configuration files
    if [ "$current_version" != "$installed_version" ]; then
        if [ "$current_version" != "dev" ] && [ "$current_version" != "testing" ]; then
            if sed -i "s|^version_locations =.*$|version_locations = ${DATABASE}_versions|" alembic.ini; then
                # Find the corresponding Alembic revision by scanning migration files
                MIGRATION_DIR="/usr/share/bunkerweb/db/alembic/${DATABASE}_versions"
                NORMALIZED_VERSION=$(echo "$current_version" | tr '.' '_' | tr '-' '_' | tr '~' '_')
                REVISION=$(find "$MIGRATION_DIR" -maxdepth 1 -type f -name "*_upgrade_to_version_${NORMALIZED_VERSION}.py" -exec basename {} \; | awk -F_ '{print $1}')

                if [ -z "$REVISION" ]; then
                    log "SYSTEMCTL" "❌" "No migration file found for database version: $current_version"
                    exit 1
                fi

                # Stamp the database with the determined revision
                if $PYTHON_BIN -m alembic stamp "$REVISION"; then
                    # Run database migration
                    log "SYSTEMCTL" "ℹ️" "Running database migration..."
                    if ! $PYTHON_BIN -m alembic upgrade head; then
                        log "SYSTEMCTL" "❌" "Database migration failed"
                        exit 1
                    fi
                    log "SYSTEMCTL" "✅" "Database migration completed successfully"
                else
                    log "SYSTEMCTL" "❌" "Failed to stamp database with revision: $REVISION, migration aborted"
                fi
            else
                log "SYSTEMCTL" "❌" "Failed to update version locations in configuration, migration aborted"
            fi
        else
            # Create temporary Python script to update version
            cat > /tmp/version_update.py << EOL
#!/usr/bin/env python3
import sqlalchemy as sa
from os import getenv

from Database import Database
from logger import getLogger

LOGGER = getLogger('SCHEDULER.SYSTEMD')

db = Database(LOGGER)
with db.sql_engine.connect() as conn:
    conn.execute(sa.text("UPDATE bw_metadata SET version = '${installed_version}' WHERE id = 1"))
EOL
            # Ensure the temporary script is readable by nginx under UMask=027
            chown root:nginx /tmp/version_update.py
            chmod 640 /tmp/version_update.py

            if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" /tmp/version_update.py; then
                log "SYSTEMCTL" "❌" "Failed to update database version (nginx user execution error)"
                rm -f /tmp/version_update.py
                exit 1
            fi
            rm -f /tmp/version_update.py
        fi
    fi

    cd - > /dev/null || exit 1

    # Execute scheduler
    log "SYSTEMCTL" "ℹ️ " "Executing scheduler ..."
    if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" /usr/share/bunkerweb/scheduler/main.py \
        --variables /etc/bunkerweb/variables.env; then
        log "SYSTEMCTL" "❌" "Scheduler execution failed (nginx user execution error)"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️ " "Scheduler stopped"
}

function stop() {
    log "SYSTEMCTL" "ℹ️" "Stopping BunkerWeb Scheduler service ..."

    if [ -f "/var/run/bunkerweb/scheduler.pid" ] ; then
        scheduler_pid=$(cat "/var/run/bunkerweb/scheduler.pid")
        log "SYSTEMCTL" "ℹ️ " "Stopping scheduler..."
        kill -SIGINT "$scheduler_pid"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Error while sending stop signal to scheduler"
            exit 1
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "Scheduler already stopped"
        return 0
    fi
    count=0
    while [ -f "/var/run/bunkerweb/scheduler.pid" ] ; do
        sleep 1
        count=$((count + 1))
        if [ $count -ge 10 ] ; then
            break
        fi
    done
    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting scheduler to stop"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️ " "BunkerWeb Scheduler service is stopped"
}

function reload()
{

    log "SYSTEMCTL" "ℹ️" "Reloading BunkerWeb Scheduler service ..."

    PID_FILE_PATH="/var/run/bunkerweb/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        result=$(cat "$PID_FILE_PATH")
        # Send signal to scheduler to reload
        log "SYSTEMCTL" "ℹ️" "Sending reload signal to scheduler ..."
        kill -SIGHUP "$result"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "SYSTEMCTL" "❌" "Your command exited with non-zero status $result"
            exit 1
        fi
    else
        log "SYSTEMCTL" "❌" "Scheduler is not running"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️" "BunkerWeb Scheduler service reloaded ..."
}

function restart() {
    log "SYSTEMCTL" "ℹ️" "Restarting BunkerWeb Scheduler service ..."
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
