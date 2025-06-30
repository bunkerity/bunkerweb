#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# Check if debug logging is enabled via LOG_LEVEL environment variable
# Returns 0 (true) if LOG_LEVEL is set to "debug" (case insensitive)
# Used throughout script to control verbose debugging output
is_debug_enabled() {
    local log_level="${LOG_LEVEL:-INFO}"
    if [[ "${log_level,,}" == "debug" ]]; then
        return 0
    fi
    return 1
}

# Enhanced logging function that respects debug level settings
# Outputs additional context information when debug mode is enabled
# Args:
#   $1: Log source/component name
#   $2: Log level/emoji indicator  
#   $3: Log message
debug_log() {
    local source="$1"
    local level="$2" 
    local message="$3"
    
    if is_debug_enabled; then
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        local pid=$$
        log "$source" "$level" "[DEBUG] [$timestamp] [PID:$pid] $message"
    else
        log "$source" "$level" "$message"
    fi
}

# Signal handler for graceful shutdown of the scheduler process
# Handles SIGTERM, SIGINT, and SIGQUIT signals to ensure clean termination
# Reads PID from /var/run/bunkerweb/scheduler.pid and sends TERM signal
# Called automatically when container receives stop signals
trap_exit() {
    # shellcheck disable=SC2317
    debug_log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
    
    if is_debug_enabled; then
        # shellcheck disable=SC2317
        debug_log "ENTRYPOINT" "ℹ️ " "Signal handler invoked, checking for PID file"
    fi
    
    # shellcheck disable=SC2317
    if [ -f "/var/run/bunkerweb/scheduler.pid" ] ; then
        # shellcheck disable=SC2317
        local scheduler_pid
        # shellcheck disable=SC2317
        scheduler_pid=$(cat /var/run/bunkerweb/scheduler.pid)
        
        if is_debug_enabled; then
            # shellcheck disable=SC2317
            debug_log "ENTRYPOINT" "ℹ️ " "Found scheduler PID: $scheduler_pid"
        fi
        
        # shellcheck disable=SC2317
        debug_log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
        # shellcheck disable=SC2317
        kill -s TERM "$scheduler_pid"
        
        if is_debug_enabled; then
            # shellcheck disable=SC2317
            debug_log "ENTRYPOINT" "ℹ️ " "TERM signal sent to PID $scheduler_pid"
        fi
    else
        if is_debug_enabled; then
            # shellcheck disable=SC2317
            debug_log "ENTRYPOINT" "ℹ️ " "No PID file found, scheduler may not be running"
        fi
    fi
}

# Setup signal trapping for graceful shutdown
# Registers trap_exit function to handle termination signals
# Ensures scheduler can be stopped cleanly during container lifecycle
setup_signal_handlers() {
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Setting up signal handlers for TERM, INT, QUIT"
    fi
    
    trap "trap_exit" TERM INT QUIT
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Signal handlers configured successfully"
    fi
}

# Clean up any existing PID file from previous runs
# Removes stale PID file that might exist from unclean shutdown
# Ensures fresh start for scheduler process tracking
cleanup_pid_file() {
    local pid_file="/var/run/bunkerweb/scheduler.pid"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Checking for existing PID file: $pid_file"
    fi
    
    if [ -f "$pid_file" ] ; then
        if is_debug_enabled; then
            local old_pid
            old_pid=$(cat "$pid_file" 2>/dev/null || echo "unknown")
            debug_log "ENTRYPOINT" "ℹ️ " "Removing stale PID file (old PID: $old_pid)"
        fi
        
        rm -f "$pid_file"
        
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "PID file cleanup completed"
        fi
    else
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "No existing PID file found"
        fi
    fi
}

# Detect and configure the deployment integration mode
# Sets integration type based on environment variables (SWARM_MODE, 
# KUBERNETES_MODE, AUTOCONF_MODE) and writes to integration file
# Used by scheduler to adapt behavior for different deployment scenarios
setup_integration_mode() {
    local integration_file="/usr/share/bunkerweb/INTEGRATION"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Detecting integration mode from environment"
        debug_log "ENTRYPOINT" "ℹ️ " "SWARM_MODE: ${SWARM_MODE:-not set}"
        debug_log "ENTRYPOINT" "ℹ️ " "KUBERNETES_MODE: ${KUBERNETES_MODE:-not set}"
        debug_log "ENTRYPOINT" "ℹ️ " "AUTOCONF_MODE: ${AUTOCONF_MODE:-not set}"
    fi
    
    if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
        echo "Swarm" > "$integration_file"
        debug_log "ENTRYPOINT" "ℹ️ " "Integration mode set to: Swarm"
    elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
        echo "Kubernetes" > "$integration_file"
        debug_log "ENTRYPOINT" "ℹ️ " "Integration mode set to: Kubernetes"
    elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
        echo "Autoconf" > "$integration_file"
        debug_log "ENTRYPOINT" "ℹ️ " "Integration mode set to: Autoconf"
    else
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "No specific integration mode detected, using default"
        fi
    fi
    
    if [ -f "$integration_file" ] && is_debug_enabled; then
        local current_mode
        current_mode=$(cat "$integration_file")
        debug_log "ENTRYPOINT" "ℹ️ " "Integration file created: $current_mode"
    fi
}

# Extract and validate the database type from DATABASE_URI
# Parses the URI scheme to determine database engine (sqlite, postgresql, etc.)
# Returns the database type for use in migration operations
# Sets up default SQLite URI if DATABASE_URI is not provided
extract_database_type() {
    # Set default database URI if not provided
    DATABASE_URI=${DATABASE_URI:-sqlite:////var/lib/bunkerweb/db.sqlite3}
    export DATABASE_URI
    
    if is_debug_enabled; then
        # Only log the scheme part for security
        local db_scheme
        db_scheme=$(echo "$DATABASE_URI" | awk -F: '{print $1}')
        debug_log "ENTRYPOINT" "ℹ️ " "Database URI scheme: $db_scheme"
    fi
    
    # Extract database type from URI scheme
    DATABASE=$(echo "$DATABASE_URI" | awk -F: '{print $1}' | awk -F+ '{print $1}')
    export DATABASE
    
    debug_log "ENTRYPOINT" "ℹ️ " "Database type detected: $DATABASE"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Database configuration exported to environment"
    fi
}

# Get the current database version using Python database connection
# Connects to the database and queries the bw_metadata table for version
# Falls back to installed version if table doesn't exist
# Handles connection errors and writes error details to temporary file
get_current_database_version() {
    local installed_version
    installed_version=$(cat /usr/share/bunkerweb/VERSION)
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Installed version: $installed_version"
        debug_log "ENTRYPOINT" "ℹ️ " "Connecting to database to check current version"
    fi
    
    local current_version
    current_version=$(python3 -c "
from os import getenv
import sqlalchemy as sa
from traceback import format_exc

from Database import Database
from logger import setup_logger

LOGGER = setup_logger('Scheduler', getenv('CUSTOM_LOG_LEVEL', getenv('LOG_LEVEL', 'INFO')))

db = None
try:
	db = Database(LOGGER)
	with db.sql_engine.connect() as conn:
		# Check if the table exists first
		inspector = sa.inspect(db.sql_engine)
		if 'bw_metadata' in inspector.get_table_names():
			result = conn.execute(sa.text('SELECT version FROM bw_metadata WHERE id = 1'))
			print(next(result)[0])
		else:
			# Table doesn't exist, use installed version
			print('${installed_version}')
except BaseException as e:
	with open('/var/tmp/bunkerweb/database_error', 'w') as file:
		file.write(format_exc())
	print('none')

if db:
	with open('/var/tmp/bunkerweb/database_uri', 'w') as file:
		file.write(db.database_uri)
")
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Database version query completed"
    fi
    
    echo "$current_version"
}

# Validate database connection and handle any errors
# Checks for error files created during database version retrieval
# Updates DATABASE_URI with the actual connection string from database object
# Exits with error code if database connection fails
validate_database_connection() {
    if [ -f /var/tmp/bunkerweb/database_error ]; then
        local error_content
        error_content=$(cat /var/tmp/bunkerweb/database_error)
        debug_log "ENTRYPOINT" "❌" "Failed to retrieve database version: $error_content"
        rm -f /var/tmp/bunkerweb/database_error
        
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Database error file cleaned up"
        fi
        
        exit 1
    elif [ ! -f /var/tmp/bunkerweb/database_uri ]; then
        debug_log "ENTRYPOINT" "❌" "Failed to retrieve database URI"
        
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Database URI file not found, connection failed"
        fi
        
        exit 1
    fi
    
    # Update DATABASE_URI with actual connection string
    DATABASE_URI=$(cat /var/tmp/bunkerweb/database_uri)
    export DATABASE_URI
    rm -f /var/tmp/bunkerweb/database_uri
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Database URI updated and temporary file cleaned up"
        debug_log "ENTRYPOINT" "ℹ️ " "Database connection validated successfully"
    fi
}

# Find the Alembic revision corresponding to a specific version
# Scans migration files to locate the revision for database version
# Uses normalized version string (dots and dashes converted to underscores)
# Returns the revision ID needed for Alembic stamping operation
find_migration_revision() {
    local current_version="$1"
    local migration_dir="/usr/share/bunkerweb/db/alembic/${DATABASE}_versions"
    local normalized_version
    normalized_version=$(echo "$current_version" | tr '.' '_' | tr '-' '_')
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Finding migration revision for version: $current_version"
        debug_log "ENTRYPOINT" "ℹ️ " "Normalized version: $normalized_version"
        debug_log "ENTRYPOINT" "ℹ️ " "Migration directory: $migration_dir"
    fi
    
    local revision
    revision=$(find "$migration_dir" -maxdepth 1 -type f \
               -name "*_upgrade_to_version_${normalized_version}.py" \
               -exec basename {} \; | awk -F_ '{print $1}')
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Migration file search completed"
        if [ -n "$revision" ]; then
            debug_log "ENTRYPOINT" "ℹ️ " "Found revision: $revision"
        else
            debug_log "ENTRYPOINT" "ℹ️ " "No revision found for version $current_version"
        fi
    fi
    
    echo "$revision"
}

# Update Alembic configuration for database migration
# Modifies alembic.ini to set correct version_locations for database type
# Required for Alembic to find the appropriate migration scripts
# Returns 0 on success, 1 on failure
update_alembic_config() {
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Updating Alembic configuration"
        debug_log "ENTRYPOINT" "ℹ️ " "Setting version_locations to: ${DATABASE}_versions"
    fi
    
    if sed -i "s|^version_locations =.*$|version_locations = ${DATABASE}_versions|" alembic.ini; then
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Alembic configuration updated successfully"
        fi
        return 0
    else
        debug_log "ENTRYPOINT" "❌" "Failed to update version locations in configuration, migration aborted"
        return 1
    fi
}

# Stamp the database with a specific Alembic revision
# Tells Alembic what revision the database is currently at
# Required before running migrations to establish baseline
# Args:
#   $1: Alembic revision ID to stamp
stamp_database_revision() {
    local revision="$1"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Stamping database with revision: $revision"
    fi
    
    if python3 -m alembic stamp "$revision"; then
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Database stamped successfully with revision $revision"
        fi
        return 0
    else
        debug_log "ENTRYPOINT" "❌" "Failed to stamp database with revision: $revision, migration aborted"
        return 1
    fi
}

# Run Alembic database migration to latest version
# Executes 'alembic upgrade head' to apply all pending migrations
# Returns 0 on success, 1 on failure
run_database_migration() {
    debug_log "ENTRYPOINT" "ℹ️" "Running database migration..."
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Executing: alembic upgrade head"
    fi
    
    if python3 -m alembic upgrade head; then
        debug_log "ENTRYPOINT" "✅" "Database migration completed successfully"
        return 0
    else
        debug_log "ENTRYPOINT" "❌" "Database migration failed"
        return 1
    fi
}

# Update database version for development/testing builds
# Directly updates the bw_metadata table for non-release versions
# Used when version is "dev" or "testing" to avoid full migration
# Args:
#   $1: Version string to set in database
update_dev_database_version() {
    local installed_version="$1"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Updating database version for dev/testing build: $installed_version"
    fi
    
    python3 -c "
import sqlalchemy as sa
from os import getenv

from Database import Database
from logger import setup_logger

LOGGER = setup_logger('Scheduler', getenv('CUSTOM_LOG_LEVEL', getenv('LOG_LEVEL', 'INFO')))

db = Database(LOGGER)
with db.sql_engine.connect() as conn:
		conn.execute(sa.text('UPDATE bw_metadata SET version = \"${installed_version}\" WHERE id = 1'))
"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Development database version update completed"
    fi
}

# Perform complete database migration process
# Handles version comparison, Alembic configuration, stamping, and migration
# Supports both release versions and development builds
# Changes to migration directory and handles all migration logic
perform_database_migration() {
    local current_version="$1"
    local installed_version="$2"
    
    debug_log "ENTRYPOINT" "ℹ️" "Checking database configuration..."
    
    # Change to Alembic directory
    cd /usr/share/bunkerweb/db/alembic || {
        debug_log "ENTRYPOINT" "❌" "Failed to access database migration directory"
        exit 1
    }
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Changed to Alembic directory: $(pwd)"
    fi
    
    debug_log "ENTRYPOINT" "ℹ️" "Checking database version..."
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Current database version: $current_version"
        debug_log "ENTRYPOINT" "ℹ️ " "Installed software version: $installed_version"
    fi
    
    # Check if migration is needed
    if [ "$current_version" != "$installed_version" ]; then
        debug_log "ENTRYPOINT" "ℹ️ " "Version mismatch detected, migration required"
        
        # Handle development/testing versions differently
        if [ "$current_version" != "dev" ] && [ "$current_version" != "testing" ]; then
            if is_debug_enabled; then
                debug_log "ENTRYPOINT" "ℹ️ " "Processing release version migration"
            fi
            
            # Update Alembic configuration
            if ! update_alembic_config; then
                exit 1
            fi
            
            # Find migration revision
            local revision
            revision=$(find_migration_revision "$current_version")
            
            if [ -z "$revision" ]; then
                debug_log "ENTRYPOINT" "❌" "No migration file found for database version: $current_version"
                exit 1
            fi
            
            # Stamp and migrate
            if stamp_database_revision "$revision"; then
                if ! run_database_migration; then
                    exit 1
                fi
            else
                exit 1
            fi
        else
            if is_debug_enabled; then
                debug_log "ENTRYPOINT" "ℹ️ " "Processing development/testing version update"
            fi
            
            update_dev_database_version "$installed_version"
        fi
    else
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Database version matches installed version, no migration needed"
        fi
    fi
    
    # Return to previous directory
    cd - > /dev/null || exit 1
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Returned to previous directory"
    fi
}

# Execute the main scheduler process
# Starts the scheduler in background and waits for completion
# Captures PID and exit code for proper process management
# Handles cleanup of health check files
start_scheduler() {
    debug_log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Starting scheduler process: /usr/share/bunkerweb/scheduler/main.py"
    fi
    
    # Start scheduler in background
    /usr/share/bunkerweb/scheduler/main.py &
    local pid="$!"
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Scheduler started with PID: $pid"
    fi
    
    # Wait for scheduler to complete
    wait "$pid"
    local exit_code=$?
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Scheduler process completed with exit code: $exit_code"
    fi
    
    # Clean up health check file
    if [ -f /var/tmp/bunkerweb/scheduler.healthy ] ; then
        rm -f /var/tmp/bunkerweb/scheduler.healthy
        
        if is_debug_enabled; then
            debug_log "ENTRYPOINT" "ℹ️ " "Removed scheduler health check file"
        fi
    fi
    
    debug_log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
    return $exit_code
}

# Main entrypoint execution flow
# Orchestrates all startup phases including signal setup, data preparation,
# integration mode detection, database migration, and scheduler execution
main() {
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "BunkerWeb Scheduler entrypoint starting"
        debug_log "ENTRYPOINT" "ℹ️ " "Debug logging enabled"
        debug_log "ENTRYPOINT" "ℹ️ " "Process ID: $$"
        debug_log "ENTRYPOINT" "ℹ️ " "User ID: $(id -u)"
        debug_log "ENTRYPOINT" "ℹ️ " "Working directory: $(pwd)"
    fi
    
    # Setup signal handlers
    setup_signal_handlers
    
    # Clean up any existing PID file
    cleanup_pid_file
    
    # Log startup message
    local version
    version=$(cat /usr/share/bunkerweb/VERSION)
    debug_log "ENTRYPOINT" "ℹ️" "Starting the job scheduler v${version} ..."
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "BunkerWeb version: $version"
    fi
    
    # Setup and check /data folder
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Setting up data folder"
    fi
    
    /usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"
    
    # Handle Docker secrets
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Processing Docker secrets"
    fi
    
    handle_docker_secrets
    
    # Setup integration mode
    setup_integration_mode
    
    # Database migration section
    extract_database_type
    
    local current_version
    current_version=$(get_current_database_version)
    
    # Validate database connection
    validate_database_connection
    
    local installed_version
    installed_version=$(cat /usr/share/bunkerweb/VERSION)
    
    # Perform migration if needed
    perform_database_migration "$current_version" "$installed_version"
    
    # Start the scheduler
    start_scheduler
    local scheduler_exit_code=$?
    
    if is_debug_enabled; then
        debug_log "ENTRYPOINT" "ℹ️ " "Entrypoint execution completed with exit code: $scheduler_exit_code"
    fi
    
    exit $scheduler_exit_code
}

# Execute main function
main "$@"