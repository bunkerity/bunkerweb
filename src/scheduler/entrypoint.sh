#!/bin/bash

# shellcheck disable=SC1091
. /usr/share/bunkerweb/helpers/utils.sh

# trap SIGTERM and SIGINT
# shellcheck disable=SC2329
function trap_exit() {
	# shellcheck disable=SC2317
	log "ENTRYPOINT" "ℹ️ " "Caught stop operation"
	# shellcheck disable=SC2317
	if [ -f "/var/run/bunkerweb/scheduler.pid" ] ; then
		# shellcheck disable=SC2317
		log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
		# shellcheck disable=SC2317
		kill -s TERM "$(cat /var/run/bunkerweb/scheduler.pid)"
	fi
}
trap "trap_exit" TERM INT QUIT

if [ -f /var/run/bunkerweb/scheduler.pid ] ; then
	rm -f /var/run/bunkerweb/scheduler.pid
fi

log "ENTRYPOINT" "ℹ️" "Starting the job scheduler v$(cat /usr/share/bunkerweb/VERSION) ..."

# setup and check /data folder
/usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

handle_docker_secrets

if [[ $(echo "$SWARM_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Swarm" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$KUBERNETES_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Kubernetes" > /usr/share/bunkerweb/INTEGRATION
elif [[ $(echo "$AUTOCONF_MODE" | awk '{print tolower($0)}') == "yes" ]] ; then
	echo "Autoconf" > /usr/share/bunkerweb/INTEGRATION
fi

export LOG_SYSLOG_TAG="${LOG_SYSLOG_TAG:-bw-scheduler}"

# Database migration section
log "ENTRYPOINT" "ℹ️" "Checking database configuration..."
cd /usr/share/bunkerweb/db/alembic || {
	log "ENTRYPOINT" "❌" "Failed to access database migration directory"
	exit 1
}

# Extract and validate database type
DATABASE_URI=${DATABASE_URI:-sqlite:////var/lib/bunkerweb/db.sqlite3}
export DATABASE_URI
DATABASE=$(echo "$DATABASE_URI" | awk -F: '{print $1}' | awk -F+ '{print $1}')

# Check current version and stamp
log "ENTRYPOINT" "ℹ️" "Checking database version..."
installed_version=$(cat /usr/share/bunkerweb/VERSION)
current_version=$(python3 -c "
from os import getenv
import sqlalchemy as sa
from traceback import format_exc

from Database import Database
from logger import getLogger

LOGGER = getLogger('SCHEDULER.ENTRYPOINT')

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

if [ -f /var/tmp/bunkerweb/database_error ]; then
	log "ENTRYPOINT" "❌" "Failed to retrieve database version: $(cat /var/tmp/bunkerweb/database_error)"
	rm -f /var/tmp/bunkerweb/database_error
	exit 1
elif [ ! -f /var/tmp/bunkerweb/database_uri ]; then
	log "ENTRYPOINT" "❌" "Failed to retrieve database URI"
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
				log "ENTRYPOINT" "❌" "No migration file found for database version: $current_version"
				exit 1
			fi

			# Stamp the database with the determined revision
			if python3 -m alembic stamp "$REVISION"; then
				# Run database migration
				log "ENTRYPOINT" "ℹ️" "Running database migration..."
				if ! python3 -m alembic upgrade head; then
					log "ENTRYPOINT" "❌" "Database migration failed"
					exit 1
				fi
				log "ENTRYPOINT" "✅" "Database migration completed successfully"
			else
				log "ENTRYPOINT" "❌" "Failed to stamp database with revision: $REVISION, migration aborted"
			fi
		else
			log "ENTRYPOINT" "❌" "Failed to update version locations in configuration, migration aborted"
		fi
	else
		python3 -c "
import sqlalchemy as sa
from os import getenv

from Database import Database
from logger import getLogger

LOGGER = getLogger('SCHEDULER')

db = Database(LOGGER)
with db.sql_engine.connect() as conn:
		conn.execute(sa.text('UPDATE bw_metadata SET version = \"${installed_version}\" WHERE id = 1'))
"
	fi
fi

cd - > /dev/null || exit 1

# execute jobs
log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
/usr/share/bunkerweb/scheduler/main.py &
pid="$!"

wait "$pid"
exit_code=$?

if [ -f /var/tmp/bunkerweb/scheduler.healthy ] ; then
	rm -f /var/tmp/bunkerweb/scheduler.healthy
fi

log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
exit $exit_code
