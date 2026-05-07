#!/usr/bin/env bash
set -euo pipefail

# Semi-automated Nginx -> BunkerWeb migration scaffold.
# - Creates a backup of source Nginx config
# - Inventories server blocks and key directives
# - Generates migration report + starter BunkerWeb compose project
# - Generates per-vhost custom snippets to speed up manual migration
#
# This script does NOT perform an in-place migration on a live host.
# It creates an output folder you can review and deploy safely.

SOURCE_DIR="/etc/nginx"
OUTPUT_DIR=""
PROJECT_NAME="bunkerweb-migrated"
BUNKERWEB_VERSION="1.6.10"
DOMAIN_FILTER=""
COPY_CERTS=0
FORCE=0

usage() {
  cat <<'EOF'
Usage:
  ./nginx2bw.sh [options]

Options:
  --source-dir PATH        Source Nginx directory (default: /etc/nginx)
  --output-dir PATH        Output folder (default: ./bunkerweb-migration-YYYYmmdd-HHMMSS)
  --project-name NAME      Docker compose project name (default: bunkerweb-migrated)
  --bunkerweb-version VER  BunkerWeb image tag (default: 1.6.10)
  --domain-filter REGEX    Only include vhosts matching regex on server_name
  --copy-certs             Copy matching cert/key files from /etc/letsencrypt/live into output/certs
  --force                  Overwrite output dir if it exists
  -h, --help               Show this help

Examples:
  ./nginx2bw.sh --source-dir /etc/nginx --copy-certs
  ./nginx2bw.sh --domain-filter 'example\\.com|example\\.org'
EOF
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Missing required command: $cmd" >&2
    exit 1
  }
}

sanitize_name() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//'
}

strip_comments() {
  sed -E 's/[[:space:]]+#.*$//; /^[[:space:]]*$/d'
}

while (($#)); do
  case "$1" in
    --source-dir)
      SOURCE_DIR="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --bunkerweb-version)
      BUNKERWEB_VERSION="$2"
      shift 2
      ;;
    --domain-filter)
      DOMAIN_FILTER="$2"
      shift 2
      ;;
    --copy-certs)
      COPY_CERTS=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd awk
require_cmd sed
require_cmd grep
require_cmd find
require_cmd tar

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$(pwd)/bunkerweb-migration-$(date +%Y%m%d-%H%M%S)"
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source dir not found: $SOURCE_DIR" >&2
  exit 1
fi

if [[ -e "$OUTPUT_DIR" && "$FORCE" -ne 1 ]]; then
  echo "Output dir already exists: $OUTPUT_DIR" >&2
  echo "Use --force to overwrite." >&2
  exit 1
fi

if [[ -e "$OUTPUT_DIR" && "$FORCE" -eq 1 ]]; then
  rm -rf "$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_DIR"/{backup,raw,snippets/server-http,snippets/http,reports,certs,project}

echo "[1/5] Backing up source nginx config..."
tar czf "$OUTPUT_DIR/backup/nginx-config-backup.tar.gz" -C "$SOURCE_DIR" .

echo "[2/5] Collecting nginx conf files..."
find "$SOURCE_DIR" -type f \( -name '*.conf' -o -name 'nginx.conf' \) | sort > "$OUTPUT_DIR/raw/conf-files.txt"

: > "$OUTPUT_DIR/reports/vhosts.csv"
echo "source_file,server_name,listen,ssl_certificate,ssl_certificate_key,proxy_pass,root" >> "$OUTPUT_DIR/reports/vhosts.csv"

TMP_BLOCK_DIR="$OUTPUT_DIR/raw/server_blocks"
mkdir -p "$TMP_BLOCK_DIR"

# Extract server blocks with simple brace counting (good enough for migration inventory).
block_idx=0
while IFS= read -r conf_file; do
  awk -v out_dir="$TMP_BLOCK_DIR" -v src="$conf_file" -v idx_start="$block_idx" '
  BEGIN { in_server=0; depth=0; idx=idx_start }
  {
    line=$0
    trimmed=line
    gsub(/^[ \t]+|[ \t]+$/, "", trimmed)

    if (!in_server && trimmed ~ /^server[ \t]*\{[ \t]*$/) {
      in_server=1
      depth=1
      idx++
      outfile=sprintf("%s/block_%08d.conf", out_dir, idx)
      print "# source: " src > outfile
      print line >> outfile
      next
    }

    if (in_server) {
      print line >> outfile
      opens=gsub(/\{/, "{", line)
      closes=gsub(/\}/, "}", line)
      depth += (opens - closes)
      if (depth <= 0) {
        in_server=0
      }
    }
  }
  END {
    print idx
  }' "$conf_file" > "$OUTPUT_DIR/raw/.last_idx"
  block_idx="$(cat "$OUTPUT_DIR/raw/.last_idx")"
done < "$OUTPUT_DIR/raw/conf-files.txt"

rm -f "$OUTPUT_DIR/raw/.last_idx"

echo "[3/5] Building migration inventory..."
shopt -s nullglob
for block in "$TMP_BLOCK_DIR"/*.conf; do
  src_file="$(sed -n '1s/^# source: //p' "$block")"

  server_name_line="$(strip_comments < "$block" | awk '/^[[:space:]]*server_name[[:space:]]+/ {print; exit}')"
  listen_line="$(strip_comments < "$block" | awk '/^[[:space:]]*listen[[:space:]]+/ {print; exit}')"
  ssl_cert_line="$(strip_comments < "$block" | awk '/^[[:space:]]*ssl_certificate[[:space:]]+/ {print; exit}')"
  ssl_key_line="$(strip_comments < "$block" | awk '/^[[:space:]]*ssl_certificate_key[[:space:]]+/ {print; exit}')"
  proxy_pass_line="$(strip_comments < "$block" | awk '/proxy_pass[[:space:]]+/ {print; exit}')"
  root_line="$(strip_comments < "$block" | awk '/^[[:space:]]*root[[:space:]]+/ {print; exit}')"

  server_name="$(echo "$server_name_line" | sed -E 's/^[[:space:]]*server_name[[:space:]]+//; s/;[[:space:]]*$//')"
  listen_val="$(echo "$listen_line" | sed -E 's/^[[:space:]]*listen[[:space:]]+//; s/;[[:space:]]*$//')"
  ssl_cert_val="$(echo "$ssl_cert_line" | sed -E 's/^[[:space:]]*ssl_certificate[[:space:]]+//; s/;[[:space:]]*$//')"
  ssl_key_val="$(echo "$ssl_key_line" | sed -E 's/^[[:space:]]*ssl_certificate_key[[:space:]]+//; s/;[[:space:]]*$//')"
  proxy_pass_val="$(echo "$proxy_pass_line" | sed -E 's/.*proxy_pass[[:space:]]+//; s/;[[:space:]]*$//')"
  root_val="$(echo "$root_line" | sed -E 's/^[[:space:]]*root[[:space:]]+//; s/;[[:space:]]*$//')"

  if [[ -n "$DOMAIN_FILTER" ]]; then
    if ! echo "$server_name" | grep -Eq "$DOMAIN_FILTER"; then
      continue
    fi
  fi

  # Keep first token for file naming (exclude wildcards/placeholders when possible).
  first_name="$(echo "$server_name" | awk '{print $1}')"
  safe_name="$(sanitize_name "${first_name:-unnamed-vhost}")"

  # Generate starter custom snippet by stripping server wrapper and directives managed by BunkerWeb.
  awk '
    BEGIN { depth=0; started=0 }
    {
      line=$0
      trimmed=line
      gsub(/^[ \t]+|[ \t]+$/, "", trimmed)

      if (!started && trimmed ~ /^server[ \t]*\{[ \t]*$/) {
        started=1
        depth=1
        next
      }

      if (started) {
        opens=gsub(/\{/, "{", line)
        closes=gsub(/\}/, "}", line)
        depth += (opens - closes)

        if (depth < 1) {
          next
        }

        if (line ~ /^[ \t]*listen[ \t]+/) next
        if (line ~ /^[ \t]*server_name[ \t]+/) next
        if (line ~ /^[ \t]*ssl_certificate[ \t]+/) next
        if (line ~ /^[ \t]*ssl_certificate_key[ \t]+/) next

        print line
      }
    }
  ' "$block" > "$OUTPUT_DIR/snippets/server-http/${safe_name}.conf"

  echo "\"$src_file\",\"$server_name\",\"$listen_val\",\"$ssl_cert_val\",\"$ssl_key_val\",\"$proxy_pass_val\",\"$root_val\"" >> "$OUTPUT_DIR/reports/vhosts.csv"

  if [[ "$COPY_CERTS" -eq 1 && -n "$ssl_cert_val" && -n "$ssl_key_val" ]]; then
    if [[ -f "$ssl_cert_val" ]]; then
      cp -f "$ssl_cert_val" "$OUTPUT_DIR/certs/${safe_name}.fullchain.pem"
    fi
    if [[ -f "$ssl_key_val" ]]; then
      cp -f "$ssl_key_val" "$OUTPUT_DIR/certs/${safe_name}.privkey.pem"
    fi
  fi
done
shopt -u nullglob

echo "[4/5] Generating BunkerWeb project scaffold..."
cat > "$OUTPUT_DIR/project/.env" <<EOF
# Generated by nginx2bw.sh
PROJECT_NAME=$PROJECT_NAME
BUNKERWEB_VERSION=$BUNKERWEB_VERSION
TZ=UTC
EOF

cat > "$OUTPUT_DIR/project/docker-compose.yml" <<'EOF'
services:
  bunkerweb:
    image: bunkerity/bunkerweb:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-bunkerweb
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      - TZ=${TZ}
      - MULTISITE=yes
      - SERVER_NAME=change-me.example.com
      - AUTO_LETS_ENCRYPT=no
      - USE_CUSTOM_SSL=yes
    volumes:
      - ../snippets:/etc/bunkerweb/custom_configs:ro
      - ../certs:/etc/bunkerweb/certs:ro
    depends_on:
      - bunkerweb-scheduler

  bunkerweb-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-scheduler
    restart: unless-stopped
    environment:
      - TZ=${TZ}
    volumes:
      - bw-data:/data

  bunkerweb-ui:
    image: bunkerity/bunkerweb-ui:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-ui
    restart: unless-stopped
    environment:
      - TZ=${TZ}
    ports:
      - "7000:7000"
    depends_on:
      - bunkerweb
      - bunkerweb-scheduler

volumes:
  bw-data:
EOF

cat > "$OUTPUT_DIR/reports/MIGRATION_REPORT.md" <<EOF
# Nginx -> BunkerWeb Migration Report

Generated at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Source dir: $SOURCE_DIR
Output dir: $OUTPUT_DIR

## What was generated

- backup/nginx-config-backup.tar.gz: full backup of source nginx directory
- reports/vhosts.csv: inventory of detected server blocks
- snippets/server-http/*.conf: starter snippets for BunkerWeb custom configs
- project/docker-compose.yml: BunkerWeb stack scaffold
- project/.env: runtime variables

## Next steps

1. Review reports/vhosts.csv and remove deprecated/duplicate vhosts.
2. Edit project/docker-compose.yml and set SERVER_NAME appropriately.
3. Review snippets/server-http/*.conf and remove directives not needed in BunkerWeb.
4. If using custom certs, map cert filenames from certs/ into BunkerWeb config.
5. Start stack from output/project:

   docker compose --env-file .env up -d

6. Validate with nginx-style checks:

   docker logs \${PROJECT_NAME}-bunkerweb --tail 200

## Important

- This is a migration accelerator, not a perfect converter.
- Always validate routing, TLS, and headers in staging before production cutover.
EOF

echo "[5/5] Done."
echo "Migration scaffold created: $OUTPUT_DIR"
echo "Read report: $OUTPUT_DIR/reports/MIGRATION_REPORT.md"
