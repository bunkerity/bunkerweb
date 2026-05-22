#!/bin/bash

# Function for printing error messages and exiting
function exit_with_error() {
  echo "❌ $1"
  exit 1
}

# Function for checking required files
function check_file_exists() {
  [ ! -f "$1" ] && exit_with_error "$1 file not found"
}

# Check required files
check_file_exists "/db/model.py"
check_file_exists "alembic.ini"
check_file_exists "env.py"
check_file_exists "script.py.mako"

# Check required environment variables
[ -z "$DATABASE" ] && exit_with_error "DATABASE environment variable is not set"
[ -z "$DATABASE_URI" ] && exit_with_error "DATABASE_URI environment variable is not set"
[ -z "$TAG" ] && exit_with_error "TAG environment variable is not set"
[ -z "$NEXT_TAG" ] && exit_with_error "NEXT_TAG environment variable is not set"
[ -z "$ONLY_UPDATE" ] && exit_with_error "ONLY_UPDATE environment variable is not set"

# Validate database type
case "$DATABASE" in
  sqlite|mariadb|mysql|postgresql|oracle)
    ;;
  *)
    exit_with_error "Unsupported database type: $DATABASE"
    ;;
esac

# Create symlink so alembic resolves {db}_versions -> versions
# (env.py overrides version_locations to "{db}_versions" but the mount is at "versions")
ln -sf versions "${DATABASE}_versions" 2>/dev/null || true

# Test database connection
echo "🔗 Testing database connection..."
python3 -c "from sqlalchemy import create_engine; create_engine('${DATABASE_URI}').connect()" || exit_with_error "Unable to connect to the database at $DATABASE_URI"
echo "✅ Database connection successful"

# Download the next tag model file
echo "📥 Downloading the model file for version $NEXT_TAG"
if ! curl -f -s -o /db/model.py "https://raw.githubusercontent.com/bunkerity/bunkerweb/refs/tags/v${NEXT_TAG}/src/common/db/model.py"; then
  echo "⚠️ Failed to download model file, using latest_model.py instead"
  if [ -f "latest_model.py" ]; then
    mv latest_model.py /db/model.py || exit_with_error "Failed to move latest_model.py to /db/model.py"
  else
    exit_with_error "Neither model download nor latest_model.py are available"
  fi
fi

# Verify the downloaded file is not an error page
if grep -q "404: Not Found" "/db/model.py"; then
  rm -f /db/model.py
  if [ -f "latest_model.py" ]; then
    mv latest_model.py /db/model.py || exit_with_error "Failed to move latest_model.py to /db/model.py"
  else
    exit_with_error "Neither model download nor latest_model.py are available"
  fi
fi

# Apply all existing migrations to bring the DB from the initial schema
# (created by the scheduler at the first tag) to the latest already-covered version.
if ls versions/*.py &>/dev/null; then
  echo "🔄 Applying existing migrations..."
  if [[ "$DATABASE" == "postgresql" ]]; then
    # PostgreSQL: apply one at a time because some migrations use
    # execute_with_new_transaction() which opens a second DB connection
    # and deadlocks during bulk upgrade head.
    while true; do
      output=$(alembic upgrade +1 2>&1)
      rc=$?
      echo "$output"
      # If no migration was applied, we've reached head — done
      if ! echo "$output" | grep -q "Running upgrade"; then
        break
      fi
      # A migration was attempted but alembic failed
      if [[ $rc -ne 0 ]]; then
        exit_with_error "Failed to apply existing migrations"
      fi
    done
  else
    # sqlite/mariadb/mysql: bulk apply is safe and fast
    alembic upgrade head || exit_with_error "Failed to apply existing migrations"
  fi
  echo "✅ Existing migrations applied"
fi

if [ "$ONLY_UPDATE" -eq 0 ]; then
  echo "🦃 Auto-generating the migration script to upgrade from $TAG to $NEXT_TAG"

  # Generate the migration script
  alembic revision --autogenerate -m "Upgrade to version $NEXT_TAG" --version-path versions || exit_with_error "Failed to create migration script for $DATABASE. Check alembic configuration or database connection."

  # Set ownership for alembic directory (optional step)
  if command -v chown &>/dev/null; then
    echo "🔧 Setting ownership for alembic directory"
    chown -R "$UID:$GID" versions || echo "⚠️ Failed to change ownership, continuing..."
  else
    echo "⚠️ 'chown' command not available, skipping ownership adjustment"
  fi

  # Apply the new migration to update the database
  echo "🔄 Applying the new migration..."
  alembic upgrade head || exit_with_error "Failed to apply the migration to the latest version"

  echo "✅ Migration script created successfully"
else
  # Set ownership for alembic directory (optional step)
  if command -v chown &>/dev/null; then
    echo "🔧 Setting ownership for alembic directory"
    chown -R "$UID:$GID" versions || echo "⚠️ Failed to change ownership, continuing..."
  else
    echo "⚠️ 'chown' command not available, skipping ownership adjustment"
  fi

  echo "✅ All migrations already applied"
fi
