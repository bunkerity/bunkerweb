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
DOMAIN_FILTER=""
COPY_CERTS=0
FORCE=0

# Default image tag: read the repo's src/VERSION when the script still lives inside the
# BunkerWeb tree, otherwise fall back to a known stable tag. Override with --bunkerweb-version.
_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -r "$_script_dir/../src/VERSION" ]]; then
  BUNKERWEB_VERSION="$(tr -d '[:space:]' < "$_script_dir/../src/VERSION")"
fi
BUNKERWEB_VERSION="${BUNKERWEB_VERSION:-1.6.9}"

usage() {
  cat <<'EOF'
Usage:
  ./nginx2bw.sh [options]

Options:
  --source-dir PATH        Source Nginx directory (default: /etc/nginx)
  --output-dir PATH        Output folder (default: ./bunkerweb-migration-YYYYmmdd-HHMMSS)
  --project-name NAME      Docker compose project name (default: bunkerweb-migrated)
  --bunkerweb-version VER  BunkerWeb image tag (default: 1.6.9)
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

# Escape a value for CSV: double any embedded quotes. (Fields are nginx paths,
# hostnames and listen/proxy values — none can begin with =/+/-/@, so spreadsheet
# formula injection is not reachable here and no leading-char guard is needed.)
csv_escape() {
  sed 's/"/""/g'
}

resolve_include_pattern() {
  local include_pattern="$1"
  local source_conf="$2"
  local source_dir
  source_dir="$(dirname "$source_conf")"

  include_pattern="${include_pattern%\"}"
  include_pattern="${include_pattern#\"}"
  include_pattern="${include_pattern%\'}"
  include_pattern="${include_pattern#\'}"

  if [[ "$include_pattern" = /* ]]; then
    printf '%s\n' "$include_pattern"
    return 0
  fi

  if compgen -G "$source_dir/$include_pattern" >/dev/null 2>&1; then
    printf '%s\n' "$source_dir/$include_pattern"
    return 0
  fi

  printf '%s\n' "$SOURCE_DIR/$include_pattern"
}

inline_server_includes() {
  local snippet_file="$1"
  local source_conf="$2"
  local expanded_file
  local include_re
  expanded_file="${snippet_file}.expanded"
  include_re='^[[:space:]]*include[[:space:]]+([^;]+)[[:space:]]*;[[:space:]]*$'

  : > "$expanded_file"

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ $include_re ]]; then
      local raw_pattern
      local resolved_pattern
      local matched=0
      raw_pattern="${BASH_REMATCH[1]}"
      resolved_pattern="$(resolve_include_pattern "$raw_pattern" "$source_conf")"

      while IFS= read -r include_file; do
        matched=1
        {
          echo "# BEGIN included from $include_file"
          cat "$include_file"
          echo "# END included from $include_file"
        } >> "$expanded_file"
      done < <(compgen -G "$resolved_pattern" || true)

      if [[ "$matched" -eq 0 ]]; then
        echo "# NOTE: unresolved include preserved for manual migration: include $raw_pattern;" >> "$expanded_file"
        echo "$line" >> "$expanded_file"
      fi
    else
      echo "$line" >> "$expanded_file"
    fi
  done < "$snippet_file"

  mv "$expanded_file" "$snippet_file"
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
# Guard so an unreadable file (common when not run as root) warns and continues
# instead of aborting the whole run under set -e. tar still archives every readable
# file before exiting non-zero, so the backup remains usable.
if ! tar czf "$OUTPUT_DIR/backup/nginx-config-backup.tar.gz" -C "$SOURCE_DIR" .; then
  echo "[warn] backup tar reported errors (unreadable files?) — continuing; review the tarball." >&2
fi

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
  BEGIN { in_server=0; depth=0; idx=idx_start; pending_server=0 }
  {
    line=$0
    trimmed=line
    gsub(/^[ \t]+|[ \t]+$/, "", trimmed)

    # Detect the start of a server block.
    # Three forms supported:
    #   server { ...        (brace on same line, optional inline directives)
    #   server\n{           (brace on next non-empty line)
    if (!in_server && !pending_server && trimmed == "server") {
      pending_server=1
      next
    }
    if (!in_server && (pending_server || trimmed ~ /^server[ \t]*\{/)) {
      if (pending_server && trimmed !~ /^\{/) {
        # Bare "server" was not followed by a brace — false positive.
        # Re-emit the buffered token to stderr (never stdout: stdout is the idx channel)
        # and process the current line normally below.
        pending_server=0
        print "server" > "/dev/stderr"
      } else {
        in_server=1
        depth=1
        idx++
        outfile=sprintf("%s/block_%08d.conf", out_dir, idx)
        print "# source: " src > outfile
        # Canonicalize the opener so every block starts with "server {" on its own
        # line. Any inline content after the first "{" (e.g. "server { listen 80;")
        # is re-emitted as the next line so directive parsing/stripping still works.
        print "server {" >> outfile
        if (!pending_server) {
          rest=substr(line, index(line, "{") + 1)
          gsub(/^[ \t]+|[ \t]+$/, "", rest)
          if (rest != "") {
            if (rest ~ /[{}"]/ || index(rest, "\47") > 0) {
              # Nested brace or a quote (\47 = single quote) on the opener line — a
              # quoted value may contain ";" or braces (e.g.
              # add_header Set-Cookie "a=1; path=/"), so keep it verbatim instead of
              # splitting inside a string. The depth counter still tracks any braces.
              print rest >> outfile
            } else {
              # Split ";"-separated inline directives onto their own lines so each
              # is parsed/stripped individually (e.g. "listen 80; server_name x;"
              # must not collapse into one line that hides server_name/root).
              parts_n=split(rest, parts, ";")
              for (pi=1; pi<=parts_n; pi++) {
                d=parts[pi]
                gsub(/^[ \t]+|[ \t]+$/, "", d)
                if (d != "") { print d ";" >> outfile }
              }
            }
          }
        }
        pending_server=0
        next
      }
    }

    if (in_server) {
      print line >> outfile
      # Count braces on a comment-stripped copy so braces inside "#" comments
      # do not corrupt the depth tracking.
      cnt=line
      sub(/#.*/, "", cnt)
      opens=gsub(/\{/, "{", cnt)
      closes=gsub(/\}/, "}", cnt)
      depth += (opens - closes)
      if (depth <= 0) {
        in_server=0
      }
    }
  }
  END {
    print idx
  }' "$conf_file" > "$OUTPUT_DIR/raw/.last_idx" || { echo "[warn] awk failed parsing $conf_file — block_idx may be stale" >&2; }
  block_idx="$(cat "$OUTPUT_DIR/raw/.last_idx")"
  # Guard against a non-numeric idx so block numbering never restarts at 1 and
  # overwrites earlier blocks.
  [[ "$block_idx" =~ ^[0-9]+$ ]] || block_idx=0
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

  # Trailing cleanup strips from the first ';' onward so a second directive or a
  # closing brace sharing the line (e.g. "proxy_pass X; }") cannot leak into the value.
  server_name="$(echo "$server_name_line" | sed -E 's/^[[:space:]]*server_name[[:space:]]+//; s/[[:space:]]*;.*$//')"
  listen_val="$(echo "$listen_line" | sed -E 's/^[[:space:]]*listen[[:space:]]+//; s/[[:space:]]*;.*$//')"
  ssl_cert_val="$(echo "$ssl_cert_line" | sed -E 's/^[[:space:]]*ssl_certificate[[:space:]]+//; s/[[:space:]]*;.*$//')"
  ssl_key_val="$(echo "$ssl_key_line" | sed -E 's/^[[:space:]]*ssl_certificate_key[[:space:]]+//; s/[[:space:]]*;.*$//')"
  proxy_pass_val="$(echo "$proxy_pass_line" | sed -E 's/.*proxy_pass[[:space:]]+//; s/[[:space:]]*;.*$//')"
  root_val="$(echo "$root_line" | sed -E 's/^[[:space:]]*root[[:space:]]+//; s/[[:space:]]*;.*$//')"

  if [[ -n "$DOMAIN_FILTER" ]]; then
    if ! echo "$server_name" | grep -Eq "$DOMAIN_FILTER"; then
      continue
    fi
  fi

  # Keep first token for naming. sanitize_name leaves a leading dot for wildcard
  # names (*.example.com -> .example.com), which would create a hidden file/dir;
  # strip it so the output is visible to mounts and tooling.
  first_name="$(echo "$server_name" | awk '{print $1}')"
  safe_name="$(sanitize_name "${first_name:-unnamed-vhost}")"
  safe_name="${safe_name#.}"
  safe_name="${safe_name:-unnamed-vhost}"

  # Scope each snippet to its own vhost via a per-server subdirectory:
  # BunkerWeb applies /data/configs/server-http/<server_name>/*.conf ONLY to that
  # server, whereas files placed directly in server-http/ apply to EVERY server.
  # A flat layout would wrongly apply every vhost's locations to all servers in a
  # multi-vhost migration, so each gets its own folder named after the vhost.
  snippet_dir="$OUTPUT_DIR/snippets/server-http/${safe_name}"
  # Collision guard: two distinct vhosts that sanitize to the same name must not
  # silently overwrite each other (the CSV would then disagree with the snippets).
  if [[ -e "$snippet_dir" ]]; then
    snippet_dir="${snippet_dir}-${block##*block_}"
    snippet_dir="${snippet_dir%.conf}"
    echo "[warn] vhost name '$safe_name' collides with an earlier vhost — writing to $(basename "$snippet_dir") (this folder name won't match a SERVER_NAME, so review/merge it manually; collisions are often case-variants of the same host)" >&2
  fi
  mkdir -p "$snippet_dir"

  # Generate starter custom snippet by stripping server wrapper and directives managed by BunkerWeb.
  snippet_file="$snippet_dir/${safe_name}.conf"

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
        # Count braces on a comment-stripped copy (same as the extraction awk) so a
        # "}" inside a "#" comment cannot drive depth to 0 and silently drop every
        # directive after it. NOTE: braces inside quoted strings are still miscounted
        # (a deeper limitation) — review snippets that use literal { } in strings.
        cnt=line
        sub(/#.*/, "", cnt)
        opens=gsub(/\{/, "{", cnt)
        closes=gsub(/\}/, "}", cnt)
        depth += (opens - closes)

        if (depth < 1) {
          next
        }

        if (line ~ /^[ \t]*listen[ \t]+/) next
        if (line ~ /^[ \t]*server_name[ \t]+/) next
        if (line ~ /^[ \t]*ssl_certificate[ \t]+/) next
        if (line ~ /^[ \t]*ssl_certificate_key[ \t]+/) next
        # Skip directives fully managed by BunkerWeb
        if (line ~ /^[ \t]*ssl_protocols[ \t]+/) next
        if (line ~ /^[ \t]*ssl_ciphers[ \t]+/) next
        if (line ~ /^[ \t]*ssl_prefer_server_ciphers[ \t]+/) next
        if (line ~ /^[ \t]*ssl_session_/) next
        if (line ~ /^[ \t]*ssl_stapling/) next
        if (line ~ /^[ \t]*access_log[ \t]+/) next
        if (line ~ /^[ \t]*error_log[ \t]+/) next
        if (line ~ /add_header[[:space:]]+(Strict-Transport-Security|X-Content-Type-Options|X-Frame-Options|X-XSS-Protection|Referrer-Policy|Content-Security-Policy)/) next

        print line
      }
    }
  ' "$block" > "$snippet_file"

  # Inline include files so external bot-control snippets are migrated with the vhost.
  inline_server_includes "$snippet_file" "$src_file"

  # Brace-balance sanity check (weak net, count on comment-stripped content so a
  # harmless "}" in a comment doesn't false-alarm). This catches a genuinely
  # unclosed block, but NOT a brace hidden in a quoted string — that case can make
  # the count cancel out while the snippet is still malformed (known limitation of
  # brace-counting; a real fix needs an nginx-aware parser). Surface it at the
  # point of use — a source-only comment would never reach the operator.
  opens="$(strip_comments < "$snippet_file" | tr -cd '{' | wc -c)"
  closes="$(strip_comments < "$snippet_file" | tr -cd '}' | wc -c)"
  if [[ "$opens" -ne "$closes" ]]; then
    printf '# WARNING: unbalanced braces (%s "{" vs %s "}") — likely a brace inside a quoted string; review by hand.\n' "$opens" "$closes" \
      | cat - "$snippet_file" > "$snippet_file.tmp" && mv "$snippet_file.tmp" "$snippet_file"
    echo "[warn] $safe_name snippet has unbalanced braces — review $snippet_file" >&2
  fi

  # CSV-escape each field to prevent injection via embedded quotes or commas.
  src_file_csv="$(printf '%s' "$src_file"   | csv_escape)"
  server_name_csv="$(printf '%s' "$server_name"  | csv_escape)"
  listen_csv="$(printf '%s' "$listen_val"    | csv_escape)"
  ssl_cert_csv="$(printf '%s' "$ssl_cert_val" | csv_escape)"
  ssl_key_csv="$(printf '%s' "$ssl_key_val"  | csv_escape)"
  proxy_csv="$(printf '%s' "$proxy_pass_val" | csv_escape)"
  root_csv="$(printf '%s' "$root_val"        | csv_escape)"
  printf '"%s","%s","%s","%s","%s","%s","%s"\n' \
    "$src_file_csv" "$server_name_csv" "$listen_csv" \
    "$ssl_cert_csv" "$ssl_key_csv" "$proxy_csv" "$root_csv" \
    >> "$OUTPUT_DIR/reports/vhosts.csv"

  if [[ "$COPY_CERTS" -eq 1 && -n "$ssl_cert_val" && -n "$ssl_key_val" ]]; then
    # Use the (collision-resolved) snippet dir name so two vhosts that share a
    # sanitized name don't overwrite each other's cert either.
    cert_name="$(basename "$snippet_dir")"
    if [[ -f "$ssl_cert_val" ]]; then
      cp -f "$ssl_cert_val" "$OUTPUT_DIR/certs/${cert_name}.fullchain.pem"
    fi
    if [[ -f "$ssl_key_val" ]]; then
      cp -f "$ssl_key_val" "$OUTPUT_DIR/certs/${cert_name}.privkey.pem"
    fi
  fi
done
shopt -u nullglob

echo "[4/5] Generating BunkerWeb project scaffold..."
cat > "$OUTPUT_DIR/project/.env" <<EOF
# Generated by nginx2bw.sh — review every value before deploying.
PROJECT_NAME=$PROJECT_NAME
BUNKERWEB_VERSION=$BUNKERWEB_VERSION
TZ=UTC
# CHANGE THESE before exposing the stack.
MYSQL_PASSWORD=changeme-db-password
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme-admin-password
EOF

# Compose modeled on misc/integrations/docker.mariadb.ui.yml (split bunkerweb +
# scheduler + UI + MariaDB). Single-quoted heredoc: \${...} are resolved by docker
# compose from the .env file at runtime, not by this script. The vhost name is
# hardcoded as change-me.example.com (NOT taken from .env) because docker compose
# only interpolates mapping VALUES, not server-name-prefixed KEYS like
# <name>_USE_TEMPLATE — replace it throughout this file with your real domain.
cat > "$OUTPUT_DIR/project/docker-compose.yml" <<'EOF'
x-bw-env: &bw-env
  # Shared DB connection string — every BunkerWeb service must agree on it.
  DATABASE_URI: "mariadb+pymysql://bunkerweb:${MYSQL_PASSWORD}@bw-db:3306/db"
  # Allow the scheduler/UI on the bw-universe subnet to reach the instance API.
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-bunkerweb
    restart: unless-stopped
    ports:
      # BunkerWeb listens unprivileged on 8080/8443 inside the container.
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp"   # QUIC / HTTP3
    labels:
      - "bunkerweb.INSTANCE=yes"
    environment:
      <<: *bw-env
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-scheduler
    restart: unless-stopped
    depends_on:
      - bunkerweb
      - bw-db
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "bunkerweb"
      TZ: "${TZ}"
      SERVER_NAME: "change-me.example.com"
      MULTISITE: "yes"
      DISABLE_DEFAULT_SERVER: "yes"
      AUTO_LETS_ENCRYPT: "no"
      USE_CLIENT_CACHE: "yes"
      USE_GZIP: "yes"
      # Secure default for a reverse-proxy stack. If a migrated vhost served static
      # files in nginx (had a `root` directive — see reports/vhosts.csv), re-enable
      # it for that server only, e.g. change-me.example.com_SERVE_FILES: "yes".
      SERVE_FILES: "no"
      # UI reverse proxy so the admin UI is reachable through BunkerWeb.
      # Replace /changeme with a hard-to-guess path.
      change-me.example.com_USE_TEMPLATE: "ui"
      change-me.example.com_USE_REVERSE_PROXY: "yes"
      change-me.example.com_REVERSE_PROXY_URL: "/changeme"
      change-me.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
      # Custom SSL: place cert/key in ../certs and uncomment per service, e.g.
      # change-me.example.com_USE_CUSTOM_SSL: "yes"
      # change-me.example.com_CUSTOM_SSL_CERT: "/data/certs/<name>.fullchain.pem"
      # change-me.example.com_CUSTOM_SSL_KEY: "/data/certs/<name>.privkey.pem"
    volumes:
      - bw-storage:/data
      # Starter snippets generated from the nginx config. The scheduler syncs
      # everything under /data/configs/<type> to the instances. Each vhost's
      # snippet lives in its own server-http/<vhost>/ subfolder, so it applies
      # only to the matching SERVER_NAME (a flat file would apply to ALL servers).
      # The <vhost> folder name must match a name listed in SERVER_NAME above.
      - ../snippets/server-http:/data/configs/server-http:ro
      - ../certs:/data/certs:ro
    networks:
      - bw-universe
      - bw-db

  bw-ui:
    image: bunkerity/bunkerweb-ui:${BUNKERWEB_VERSION}
    container_name: ${PROJECT_NAME}-ui
    restart: unless-stopped
    depends_on:
      - bw-db
    environment:
      <<: *bw-env
      TZ: "${TZ}"
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
    networks:
      - bw-universe
      - bw-db

  bw-db:
    image: mariadb:11
    container_name: ${PROJECT_NAME}-db
    restart: unless-stopped
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "${MYSQL_PASSWORD}"
    volumes:
      - bw-data:/var/lib/mysql
    networks:
      - bw-db

volumes:
  bw-data:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        # Change this subnet if 10.20.30.0/24 conflicts with your host/VPN range
        # (BunkerWeb's own dev compose uses the same CIDR — stop that stack first
        # or pick a different subnet here, and keep API_WHITELIST_IP in sync).
        - subnet: 10.20.30.0/24
  bw-services:
    name: bw-services
  bw-db:
    name: bw-db
EOF

cat > "$OUTPUT_DIR/reports/MIGRATION_REPORT.md" <<EOF
# Nginx -> BunkerWeb Migration Report

Generated at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Source dir: $SOURCE_DIR
Output dir: $OUTPUT_DIR

## What was generated

- backup/nginx-config-backup.tar.gz: full backup of source nginx directory
- reports/vhosts.csv: inventory of detected server blocks
- snippets/server-http/<vhost>/<vhost>.conf: per-vhost starter snippets (one
  folder per server, so each applies only to its own SERVER_NAME)
- project/docker-compose.yml: BunkerWeb stack scaffold
- project/.env: runtime variables

## Next steps

1. Review reports/vhosts.csv and remove deprecated/duplicate vhosts.
2. Edit project/.env: set MYSQL_PASSWORD, ADMIN_USERNAME and ADMIN_PASSWORD
   (the defaults are placeholders — do not deploy them as-is). Then replace
   change-me.example.com throughout project/docker-compose.yml with your real
   vhost (it is hardcoded there, not in .env, because compose cannot interpolate
   the <name>_* setting keys). For multiple vhosts, add each to SERVER_NAME
   (space-separated) and give each its own <name>_USE_REVERSE_PROXY / etc. block.
3. Review snippets/server-http/<vhost>/<vhost>.conf and remove directives not
   needed in BunkerWeb. The whole snippets/server-http tree is mounted read-only
   at /data/configs/server-http and synced to the instance; each <vhost>/ folder
   scopes its snippet to the matching SERVER_NAME, so the folder name must appear
   in SERVER_NAME for the snippet to take effect.
4. For custom certs, files in certs/ are mounted at /data/certs in the scheduler.
   Uncomment the <name>_USE_CUSTOM_SSL / _CUSTOM_SSL_CERT / _CUSTOM_SSL_KEY lines
   in docker-compose.yml and point them at /data/certs/<name>.*.pem.
5. Start stack from project/:

   cd project && docker compose up -d

6. Validate:

   docker compose logs bw-scheduler --tail 200   # instance configured?
   docker compose logs bunkerweb --tail 200       # serving on :80 / :443?

   The admin UI is reachable through BunkerWeb at https://<SERVER_NAME>/changeme
   (change that path in docker-compose.yml).

## Important

- This is a migration accelerator, not a perfect converter.
- Always validate routing, TLS, and headers in staging before production cutover.
EOF

echo "[5/5] Done."
echo "Migration scaffold created: $OUTPUT_DIR"
echo "Read report: $OUTPUT_DIR/reports/MIGRATION_REPORT.md"
