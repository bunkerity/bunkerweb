#!/bin/bash

# Optimized migration script
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

while :; do
  resp=$(curl -s "https://api.github.com/repos/bunkerity/bunkerweb/tags?per_page=100&page=$page")
  # Stop when an empty array is returned
  [[ $(jq 'length' <<<"$resp") -eq 0 ]] && break
  all_tags_json+=( "$resp" )
  ((page++))
done

# 2) Extract, normalize, filter and sort
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

# Process each tag and database combination
log "🏗️ Processing migration tags and databases"
NEXT_TAG="dev"
jq -r 'to_entries[] | "\(.key) \(.value)"' databases.json | while read -r database database_uri; do
  started=0

  for tag in $(echo "$tags" | jq -r '.[]'); do
    if [ "$tag" == "$NEXT_TAG" ]; then
      continue
    fi

    # Skip Oracle migrations for versions earlier than 1.6.2-rc1
    if [[ "$database" == "oracle" ]] && version_lt "$tag" "1.6.2-rc1"; then
      log "⏭️ Skipping Oracle migration for version $tag (Oracle support starts from 1.6.2-rc1)"
      continue
    fi

    export DATABASE="$database"
    export DATABASE_URI="${database_uri//+psycopg}"

    if [[ "$started" -eq 0 ]]; then
      tag_index=$(echo "$tags" | jq -r --arg current_tag "$tag" 'index($current_tag)')
      next_tag_index=$((tag_index + 1))
      export TAG="$tag"
      NEXT_TAG=$(echo "$tags" | jq -r --argjson idx "$next_tag_index" '.[$idx] // empty')
      export NEXT_TAG

      if [[ -z "$NEXT_TAG" ]]; then
        log "🔚 Skipping migration for the last tag $tag"
        continue
      fi

      log "✨ Creating migration scripts from version $TAG to $NEXT_TAG and database $database"

      started=1

      # Start the database stack if not SQLite
      if [[ "$database" != "sqlite" ]]; then
        log "🚀 Starting Docker stack for $database"
        docker compose -f "$database.yml" pull || true
        if ! docker compose -f "$database.yml" up -d; then
          log "❌ Failed to start the Docker stack for $database"
          docker compose down -v --remove-orphans
          find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} +
          exit 1
        fi
      fi

      log "🚀 Starting Docker stack for BunkerWeb"
      if ! docker compose up -d; then
        log "❌ Failed to start the Docker stack for BunkerWeb"
        docker compose down -v --remove-orphans
        find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} +
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
        find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} +
        exit 1
      fi

      log "✅ Scheduler is healthy"

      docker compose stop bw-scheduler bunkerweb || true
    else
      export NEXT_TAG="$tag"

      if [[ -z "$NEXT_TAG" ]]; then
        log "🔚 Skipping migration for the last tag $tag"
        continue
      fi

      log "✨ Creating migration scripts from version $TAG to $NEXT_TAG and database $database"
    fi

    transformed_tag="${NEXT_TAG//[.~-]/_}.py"
    migration_dir="${db_dir}/alembic/${database}_versions"

    # Skip if migration script already exists
    export ONLY_UPDATE=0
    if compgen -G "$migration_dir"/*_"$transformed_tag" > /dev/null; then
      log "🔄 Migration scripts for version $tag and database $database already exist"
      export ONLY_UPDATE=1
    fi

    export DATABASE_URI="$database_uri"

    # Run the migration script
    log "🦃 Running migration script for $tag and $database"
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
      find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} +
      exit 1
    fi

    export TAG="$tag"

    echo ""
  done

  # Clean up Docker stack
  log "🧹 Cleaning up Docker stack"
  docker compose down -v --remove-orphans
done

log "🎉 Migration scripts generation completed"

# Final cleanup
log "🛑 Stopping and cleaning up any remaining Docker stacks"
docker compose down -v --remove-orphans || true
find "$db_dir" -type d -name "__pycache__" -exec rm -rf {} +

cd "$current_dir" || exit
