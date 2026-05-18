#!/bin/bash

# Migration script — always boots scheduler at the original tag (1.5.0-beta),
# applies all existing migrations in bulk, then generates only the new one.
set -euo pipefail

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Version comparison function for regular, beta, and rc versions
version_lt() {
  # For identical versions, compare the full strings
  if [[ "$1" == "$2" ]]; then
    return 1
  fi

  # Extract main version numbers
  local v1_main
  v1_main=$(echo "$1" | sed -E 's/([0-9]+\.[0-9]+\.[0-9]+).*/\1/')
  local v2_main
  v2_main=$(echo "$2" | sed -E 's/([0-9]+\.[0-9]+\.[0-9]+).*/\1/')

  # If main versions are different, compare them
  if [[ "$v1_main" != "$v2_main" ]]; then
    if [[ "$(printf '%s\n' "$v1_main" "$v2_main" | sort -V | head -n1)" == "$v1_main" ]]; then
      return 0  # v1 is less than v2
    else
      return 1  # v1 is greater than v2
    fi
  fi

  # Main versions are equal, check for beta/rc suffixes
  local v1_suffix
  v1_suffix=$(echo "$1" | grep -oE '(beta|rc)[0-9]*$' || echo "")
  local v2_suffix
  v2_suffix=$(echo "$2" | grep -oE '(beta|rc)[0-9]*$' || echo "")

  # No suffix is higher than any suffix
  if [[ -z "$v1_suffix" && -n "$v2_suffix" ]]; then
    return 1  # v1 is greater (no suffix)
  elif [[ -n "$v1_suffix" && -z "$v2_suffix" ]]; then
    return 0  # v1 is less (has suffix)
  elif [[ -z "$v1_suffix" && -z "$v2_suffix" ]]; then
    return 1  # Both have no suffix, they're equal (already checked for exact equality)
  fi

  # Both have suffixes - beta is less than rc
  if [[ "$v1_suffix" == beta* && "$v2_suffix" == rc* ]]; then
    return 0  # v1 (beta) is less than v2 (rc)
  elif [[ "$v1_suffix" == rc* && "$v2_suffix" == beta* ]]; then
    return 1  # v1 (rc) is greater than v2 (beta)
  fi

  # Same type of suffix, compare the numbers
  local type1
  type1=$(echo "$v1_suffix" | grep -oE '^(beta|rc)')
  local type2
  type2=$(echo "$v2_suffix" | grep -oE '^(beta|rc)')
  local num1
  num1=$(echo "$v1_suffix" | grep -oE '[0-9]+$' || echo "0")
  local num2
  num2=$(echo "$v2_suffix" | grep -oE '[0-9]+$' || echo "0")

  if [[ "$type1" == "$type2" && "$num1" -lt "$num2" ]]; then
    return 0  # v1 is less than v2
  else
    return 1  # v1 is not less than v2
  fi
}

# Fetch and process tags
log "🌐 Fetching tags from GitHub"
page=1
all_tags_json=()
github_auth=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  github_auth=(-H "Authorization: token $GITHUB_TOKEN")
fi

while :; do
  if ! resp=$(curl -sf "${github_auth[@]}" \
    "https://api.github.com/repos/bunkerity/bunkerweb/tags?per_page=100&page=$page"); then
    log "❌ GitHub API request failed (rate limited or network error)"
    log "💡 Set GITHUB_TOKEN to increase rate limit (60/hr → 5000/hr)"
    exit 1
  fi
  # Verify the response is a JSON array (error objects are not arrays)
  if [[ "$(jq -r 'type' <<<"$resp")" != "array" ]]; then
    log "❌ Unexpected GitHub API response: $(jq -r '.message // "unknown error"' <<<"$resp")"
    exit 1
  fi
  [[ $(jq 'length' <<<"$resp") -eq 0 ]] && break
  all_tags_json+=("$resp")
  ((page++))
done

# Extract, normalize, filter and sort (oldest first)
tags=$(printf '%s\n' "${all_tags_json[@]}" \
  | jq -r '.[].name | sub("^v"; "")' \
  | jq -R -s -c '
      split("\n")[:-1]
      | map(
          select(
            test(
              "^[1-9]+\\.(?:5(?:\\.\\d+)?(?:-beta)?|[6-9]|[1-9][0-9]+)"
            )
          )
        )
      | reverse
    ')

current_dir=$(basename "$(pwd)")

# Navigate to the root directory if in a subdirectory
case "$current_dir" in
  migration) cd ../.. ;;
  misc) cd .. ;;
esac

if [[ ! -f src/VERSION ]]; then
  log "❌ src/VERSION file not found"
  exit 1
fi

# Read and validate the current version
current_version=$(<src/VERSION)
if [[ "$current_version" != "dev" && "$current_version" != "testing" ]]; then
  tags=$(echo "$tags" | jq -c --arg version "$current_version" 'if index($version) == null then . + [$version] else . end')
fi

# Build the Docker image
log "🐳 Building Docker image for migration"
docker build -t local/bw-migration -f misc/migration/Dockerfile .

# Ensure we're in the migration directory
cd misc/migration || exit 1

db_dir=$(realpath ../../src/common/db)

# Process each database
log "🏗️ Processing migration tags and databases"
mapfile -t db_entries < <(grep -v '^\s*//' databases.json | jq -r 'to_entries[] | "\(.key) \(.value)"')
for entry in "${db_entries[@]}"; do
  read -r database database_uri <<< "$entry"
  migration_dir="${db_dir}/alembic/${database}_versions"

  # Build the tags array
  mapfile -t tags_array < <(echo "$tags" | jq -r '.[]')
  total=${#tags_array[@]}

  if [[ $total -lt 2 ]]; then
    log "⚠️ Not enough tags to generate migrations, skipping"
    continue
  fi

  target_tag="${tags_array[$((total - 1))]}"

  # Check if the target tag already has a migration
  transformed_target="${target_tag//[.~-]/_}.py"
  has_target_migration=0
  if compgen -G "$migration_dir"/*_"$transformed_target" > /dev/null; then
    has_target_migration=1
  fi

  # Always boot the scheduler at the first tag to create the initial DB schema
  first_tag="${tags_array[0]}"
  if [[ "$database" == "oracle" ]]; then
    for ((i = 0; i < total; i++)); do
      if ! version_lt "${tags_array[$i]}" "1.6.2-rc1"; then
        first_tag="${tags_array[$i]}"
        break
      fi
    done
  fi

  if [[ $has_target_migration -eq 1 ]]; then
    log "🔄 Migration exists for $target_tag ($database), testing it"
  else
    log "✨ Generating migration for $database: $first_tag → $target_tag"
  fi

  export DATABASE="$database"
  export TAG="$first_tag"
  export NEXT_TAG="$target_tag"

  # Start the database stack if not SQLite
  export DATABASE_URI="${database_uri//+psycopg}"
  if [[ "$database" != "sqlite" ]]; then
    log "🚀 Starting Docker stack for $database"
    docker compose -f "$database.yml" pull || true
    if ! docker compose -f "$database.yml" up -d; then
      log "❌ Failed to start the Docker stack for $database"
      docker compose down -v --remove-orphans
      find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
      exit 1
    fi
  fi

  log "🚀 Starting Docker stack for BunkerWeb"
  if ! docker compose up -d; then
    log "❌ Failed to start the Docker stack for BunkerWeb"
    docker compose down -v --remove-orphans
    find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    exit 1
  fi

  # Wait for the scheduler to be healthy
  log "⏳ Waiting for the scheduler to become healthy"
  timeout=60
  until docker compose ps bw-scheduler | grep -q "(healthy)" || [[ $timeout -le 0 ]]; do
    sleep 5
    timeout=$((timeout - 5))
  done

  if [[ $timeout -le 0 ]]; then
    log "❌ Timeout waiting for the scheduler to be healthy"
    docker compose logs bw-scheduler
    docker compose down -v --remove-orphans
    find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    exit 1
  fi

  log "✅ Scheduler is healthy"
  docker compose stop bw-scheduler bunkerweb || true

  export ONLY_UPDATE="$has_target_migration"
  # Strip +psycopg to use psycopg2 — psycopg3 opens two connections during
  # bulk 'alembic upgrade head' which deadlocks on PostgreSQL table locks.
  export DATABASE_URI="${database_uri//+psycopg}"

  # Run the migration (applies existing migrations in bulk + generates new one)
  log "🦃 Running migration for $first_tag → $target_tag ($database)"
  if ! docker run --rm \
    --network=bw-db \
    -v bw-data:/data \
    -v bw-db:/db \
    -v bw-sqlite:/var/lib/bunkerweb \
    -v "$migration_dir":/usr/share/migration/versions \
    -e TAG \
    -e DATABASE \
    -e DATABASE_URI \
    -e NEXT_TAG \
    -e ONLY_UPDATE \
    -e UID="$(id -u)" \
    -e GID="$(id -g)" \
    local/bw-migration; then
    log "❌ Failed to run the migration script"
    docker compose down -v --remove-orphans
    find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    exit 1
  fi

  # Clean up Docker stack
  log "🧹 Cleaning up Docker stack"
  docker compose down -v --remove-orphans
done

log "🎉 Migration scripts generation completed"

# Final cleanup
log "🛑 Stopping and cleaning up any remaining Docker stacks"
docker compose down -v --remove-orphans || true
find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
