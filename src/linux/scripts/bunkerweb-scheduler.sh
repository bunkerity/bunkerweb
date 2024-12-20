#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Set the PYTHONPATH
export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db

# Create the scheduler.env file if it doesn't exist
if [ ! -f /etc/bunkerweb/scheduler.env ]; then
    {
        echo "LOG_LEVEL=info"
        echo "LOG_TO_FILE=yes"
        echo "HEALTHCHECK_INTERVAL=30 # in seconds"
        echo "RELOAD_MIN_TIMEOUT=5 # in seconds (the minimum is calculated by the formula and whichever is greater: RELOAD_MIN_TIMEOUT or count(SERVERS) * 2))"
    } > /etc/bunkerweb/scheduler.env
    chown root:nginx /etc/bunkerweb/scheduler.env
    chmod 660 /etc/bunkerweb/scheduler.env
fi

# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload]"
    echo "Options:"
    echo "  start:   Create configurations and run necessary jobs for the bunkerweb service."
    echo "  stop:    Stop the bunkerweb scheduler service."
    echo "  reload:  Reload the bunkerweb scheduler service."
}

# Start the bunkerweb service
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb Scheduler service ..."

    # Check if the scheduler is already running
    stop

    CUSTOM_LOG_LEVEL="$(grep "^LOG_LEVEL=" /etc/bunkerweb/scheduler.env | cut -d '=' -f 2)"
    export CUSTOM_LOG_LEVEL

    SCHEDULER_LOG_TO_FILE="$(grep "^SCHEDULER_LOG_TO_FILE=" /etc/bunkerweb/variables.env | cut -d '=' -f 2)"
    if [ -z "$SCHEDULER_LOG_TO_FILE" ] ; then
        SCHEDULER_LOG_TO_FILE="$(grep "^LOG_TO_FILE=" /etc/bunkerweb/scheduler.env | cut -d '=' -f 2)"

        if [ -z "$SCHEDULER_LOG_TO_FILE" ] ; then
            SCHEDULER_LOG_TO_FILE="yes"
        fi
    fi
    export SCHEDULER_LOG_TO_FILE

    # Database migration section
    log "SYSTEMCTL" "ℹ️" "Checking database configuration..."
    cd /usr/share/bunkerweb/db/alembic || {
        log "SYSTEMCTL" "❌" "Failed to access database migration directory"
        exit 1
    }

    # Extract and validate database type
    DATABASE_URI=${DATABASE_URI:-sqlite:////var/lib/bunkerweb/db.sqlite3}
    DATABASE=$(echo "$DATABASE_URI" | awk -F: '{print $1}' | awk -F+ '{print $1}')

    # Validate database type with case-insensitive comparison
    db_type=$(echo "$DATABASE" | tr '[:upper:]' '[:lower:]')
    case "$db_type" in
        sqlite|mysql|mariadb|postgresql)
            log "SYSTEMCTL" "ℹ️" "Using database type: $DATABASE"
            ;;
        *)
            log "SYSTEMCTL" "❌" "Unsupported database type: $DATABASE"
            exit 1
            ;;
    esac

    # Update configuration files
    if ! sed -i "s|^sqlalchemy\\.url =.*$|sqlalchemy.url = $DATABASE_URI|" alembic.ini; then
        log "SYSTEMCTL" "❌" "Failed to update database URL in configuration"
        exit 1
    fi

    if ! sed -i "s|^version_locations =.*$|version_locations = ${DATABASE}_versions|" alembic.ini; then
        log "SYSTEMCTL" "❌" "Failed to update version locations in configuration"
        exit 1
    fi

    # Check current version and stamp
    log "SYSTEMCTL" "ℹ️" "Checking database version..."
    installed_version=$(cat /usr/share/bunkerweb/VERSION)
    # Create temporary Python script
    cat > /tmp/version_check.py << EOL
import sqlalchemy as sa
from os import getenv

from Database import Database
from logger import setup_logger

LOGGER = setup_logger('Scheduler', getenv('CUSTOM_LOG_LEVEL', getenv('LOG_LEVEL', 'INFO')))

engine = Database(LOGGER, '${DATABASE_URI}').sql_engine
with engine.connect() as conn:
    try:
        result = conn.execute(sa.text('SELECT version FROM bw_metadata WHERE id = 1'))
        print(next(result)[0])
    except BaseException as e:
        if 'doesn\\'t exist' not in str(e):
            print('none')
        print('${installed_version}')
EOL

    current_version=$(sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 /tmp/version_check.py")
    rm -f /tmp/version_check.py

    if [ "$current_version" == "none" ]; then
        log "SYSTEMCTL" "❌" "Failed to retrieve database version"
        exit 1
    fi

    if [ "$current_version" != "$installed_version" ]; then
        # Find the corresponding Alembic revision by scanning migration files
        MIGRATION_DIR="/usr/share/bunkerweb/db/alembic/${DATABASE}_versions"
        NORMALIZED_VERSION=$(echo "$current_version" | tr '.' '_' | tr '-' '_')
        REVISION=$(find "$MIGRATION_DIR" -maxdepth 1 -type f -name "*_upgrade_to_version_${NORMALIZED_VERSION}.py" -exec basename {} \; | awk -F_ '{print $1}')

        if [ -z "$REVISION" ]; then
            log "SYSTEMCTL" "❌" "No migration file found for database version: $current_version"
            exit 1
        fi

        # Stamp the database with the determined revision
        if ! sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m alembic stamp \"$REVISION\""; then
            log "SYSTEMCTL" "❌" "Failed to stamp database with revision: $REVISION"
            exit 1
        fi

        # Run database migration
        log "SYSTEMCTL" "ℹ️" "Running database migration..."
        if ! sudo -E -u nginx -g nginx /bin/bash -c "PYTHONPATH=$PYTHONPATH python3 -m alembic upgrade head"; then
            log "SYSTEMCTL" "❌" "Database migration failed"
            exit 1
        fi

        log "SYSTEMCTL" "✅" "Database migration completed successfully"
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
    *)
    echo "Invalid option!"
    echo "List of options availables:"
    display_help
esac
