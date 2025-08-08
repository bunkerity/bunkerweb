#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db

# Helper function to extract variables with fallback
function get_env_var() {
    local var_name=$1
    local default_value=$2
    local value

    # First try scheduler.env
    value=$(grep "^${var_name}=" /etc/bunkerweb/scheduler.env 2>/dev/null | cut -d '=' -f 2-)

    # If not found, try variables.env
    if [ -z "$value" ] && [ -f /etc/bunkerweb/variables.env ]; then
        value=$(grep "^${var_name}=" /etc/bunkerweb/variables.env 2>/dev/null | cut -d '=' -f 2-)
    fi

    # Return default if still not found
    if [ -z "$value" ]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

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
            echo "LOG_TO_FILE=yes"
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

    # Extract environment variables with fallback
    CUSTOM_LOG_LEVEL=$(get_env_var "LOG_LEVEL" "INFO")
    export CUSTOM_LOG_LEVEL

    SCHEDULER_LOG_TO_FILE=$(get_env_var "SCHEDULER_LOG_TO_FILE" "")
    if [ -z "$SCHEDULER_LOG_TO_FILE" ]; then
        SCHEDULER_LOG_TO_FILE=$(get_env_var "LOG_TO_FILE" "yes")
    fi
    export SCHEDULER_LOG_TO_FILE

    # Extract DATABASE_URI with fallback
    DATABASE_URI=$(get_env_var "DATABASE_URI" "sqlite:////var/lib/bunkerweb/db.sqlite3")
    export DATABASE_URI

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
from os import getenv
import sqlalchemy as sa
from traceback import format_exc

from Database import Database
from logger import setup_logger

LOGGER = setup_logger("Scheduler", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

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

    current_version=$(sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 /tmp/version_check.py")
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
                NORMALIZED_VERSION=$(echo "$current_version" | tr '.' '_' | tr '-' '_')
                REVISION=$(find "$MIGRATION_DIR" -maxdepth 1 -type f -name "*_upgrade_to_version_${NORMALIZED_VERSION}.py" -exec basename {} \; | awk -F_ '{print $1}')

                if [ -z "$REVISION" ]; then
                    log "SYSTEMCTL" "❌" "No migration file found for database version: $current_version"
                    exit 1
                fi

                # Stamp the database with the determined revision
                if python3 -m alembic stamp "$REVISION"; then
                    # Run database migration
                    log "SYSTEMCTL" "ℹ️" "Running database migration..."
                    if ! python3 -m alembic upgrade head; then
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
import sqlalchemy as sa
from os import getenv

from Database import Database
from logger import setup_logger

LOGGER = setup_logger('Scheduler', getenv('CUSTOM_LOG_LEVEL', getenv('LOG_LEVEL', 'INFO')))

db = Database(LOGGER)
with db.sql_engine.connect() as conn:
    conn.execute(sa.text("UPDATE bw_metadata SET version = '${installed_version}' WHERE id = 1"))
EOL

            sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 /tmp/version_update.py"
            rm -f /tmp/version_update.py
        fi
    fi

    cd - > /dev/null || exit 1

    # Execute scheduler
    log "SYSTEMCTL" "ℹ️ " "Executing scheduler ..."
    sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH /usr/share/bunkerweb/scheduler/main.py --variables /etc/bunkerweb/variables.env"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "SYSTEMCTL" "❌" "Scheduler failed"
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
