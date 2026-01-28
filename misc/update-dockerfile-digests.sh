#!/usr/bin/env bash
set -euo pipefail

# Update Dockerfile image digests under src/.
# Finds FROM lines pinned with @sha256:... and refreshes the digest for the tag.
#
# Requires:
#   - docker
#   - docker buildx
#
# Usage:
#   ./update-dockerfile-digests.optimized.sh [--dry-run] [--root PATH] [-v]

DRY_RUN=0
VERBOSE=0
ROOT=""

usage() {
  cat <<'EOF'
Usage: update-dockerfile-digests.optimized.sh [--dry-run] [--root PATH] [-v]
  --dry-run      Do not modify files; only report what would change
  --root PATH    Project root (default: git top-level or current directory)
  -v, --verbose  Verbose logs
EOF
}

log()  { printf '%s\n' "$*"; }
vlog() { (( VERBOSE )) && printf '%s\n' "$*" >&2 || true; }

# Parse args (backward compatible: works with a lone "--dry-run")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --root) ROOT="${2:?missing value for --root}"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${ROOT}" ]]; then
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
docker buildx version >/dev/null 2>&1 || { echo "docker buildx is required" >&2; exit 1; }

SRC_DIR="${ROOT%/}/src"
if [[ ! -d "$SRC_DIR" ]]; then
  echo "No src/ directory found under: $ROOT" >&2
  exit 1
fi

# Collect Dockerfiles under src/ (including src/linux and any other subtrees)
mapfile -d '' dockerfiles < <(
  find "$SRC_DIR" -type f -name 'Dockerfile*' -print0 2>/dev/null \
  | LC_ALL=C sort -zu
)

if (( ${#dockerfiles[@]} == 0 )); then
  echo "No Dockerfiles found under src/" >&2
  exit 1
fi

declare -A digest_by_image
declare -A image_set

# Extract the image reference token from a Dockerfile FROM line.
# Supports:
#   FROM image:tag@sha256:... AS stage
#   FROM --platform=linux/amd64 image:tag@sha256:... AS stage
# Returns the image ref token on stdout, or empty on non-FROM/unparsable.
extract_from_image_ref() {
  local line="$1"

  # Trim leading spaces
  line="${line#"${line%%[![:space:]]*}"}"
  [[ "$line" == FROM\ * ]] || return 1

  # Strip the leading "FROM "
  line="${line#FROM }"

  # Iterate tokens; skip flags like --platform=..., pick first non-flag token as image ref
  local tok
  for tok in $line; do
    [[ "${tok^^}" == "AS" ]] && break
    if [[ "$tok" == --* ]]; then
      continue
    fi
    printf '%s\n' "$tok"
    return 0
  done

  return 1
}

get_manifest_digest() {
  local image="$1"
  local out digest
  local attempt=1 max_attempts=3

  while (( attempt <= max_attempts )); do
    if out="$(docker buildx imagetools inspect "$image" 2>/dev/null)"; then
      digest="$(
        awk -F': ' 'tolower($1)=="digest" {print $2; exit}' <<<"$out" \
          | tr -d '\r' \
          | sed 's/^[[:space:]]*//'
      )"
      if [[ "$digest" == sha256:* ]]; then
        printf '%s\n' "$digest"
        return 0
      fi
    fi

    vlog "Failed to fetch digest for $image (attempt $attempt/$max_attempts)"
    sleep $(( attempt * 1 ))
    (( attempt++ ))
  done

  echo "Failed to fetch digest for ${image} via docker buildx imagetools inspect" >&2
  return 1
}

# Scan Dockerfiles and build the unique set of images that are pinned with @sha256:...
for dockerfile in "${dockerfiles[@]}"; do
  while IFS= read -r line || [[ -n "$line" ]]; do
    image_ref="$(extract_from_image_ref "$line" || true)"
    [[ -z "${image_ref:-}" ]] && continue

    if [[ "$image_ref" =~ ^([^@]+)@sha256:[0-9a-f]{64}$ ]]; then
      image_set["${BASH_REMATCH[1]}"]=1
    fi
  done < "$dockerfile"
done

if (( ${#image_set[@]} == 0 )); then
  log "No pinned @sha256 digests found in Dockerfiles. Nothing to do."
  exit 0
fi

# Fetch digests sequentially (often fastest overall due to lower overhead and registry throttling)
for image in "${!image_set[@]}"; do
  log "Fetching digest for ${image}..."
  digest_by_image["$image"]="$(get_manifest_digest "$image")"
done

tmpdir="$(mktemp -d -t bw-dockerfile-digests.XXXXXX)"
cleanup() { rm -rf "$tmpdir"; }
trap cleanup EXIT

# Rewrite a Dockerfile to stdout; return 0 if changed, 2 if unchanged.
update_file() {
  local path="$1"
  local changed=0
  local line image_ref image_no_digest digest new_ref

  while IFS= read -r line || [[ -n "$line" ]]; do
    image_ref="$(extract_from_image_ref "$line" || true)"
    if [[ -n "${image_ref:-}" && "$image_ref" =~ ^([^@]+)@sha256:[0-9a-f]{64}$ ]]; then
      image_no_digest="${BASH_REMATCH[1]}"
      digest="${digest_by_image[$image_no_digest]-}"
      if [[ -z "$digest" ]]; then
        echo "No cached digest for ${image_no_digest}" >&2
        return 1
      fi

      new_ref="${image_no_digest}@${digest}"
      if [[ "$new_ref" != "$image_ref" ]]; then
        changed=1
        # Replace only the image token once; preserve original spacing/flags/AS/comments.
        line="${line/$image_ref/$new_ref}"
      fi
    fi
    printf '%s\n' "$line"
  done < "$path"

  (( changed )) && return 0
  return 2
}

changed_files=()

for dockerfile in "${dockerfiles[@]}"; do
  log "Updating ${dockerfile}..."
  tmpfile="$(mktemp -p "$tmpdir" -t bw-dockerfile-update.XXXXXX)"
  if update_file "$dockerfile" > "$tmpfile"; then
    if (( DRY_RUN == 0 )); then
      cat "$tmpfile" > "$dockerfile"
    fi
    changed_files+=("$dockerfile")
  else
    status=$?
    if [[ $status -ne 2 ]]; then
      exit 1
    fi
  fi
done

if (( DRY_RUN )); then
  log "Would update:"
  for path in "${changed_files[@]}"; do
    log "- ${path}"
  done
else
  if (( ${#changed_files[@]} )); then
    log "Updated:"
    for path in "${changed_files[@]}"; do
      log "- ${path}"
    done
  else
    log "No changes needed."
  fi
fi
