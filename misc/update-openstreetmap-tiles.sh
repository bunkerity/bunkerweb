#!/usr/bin/env bash
set -euo pipefail

# If we're in "misc", cd ..
if [[ "$(basename "$PWD")" == "misc" ]]; then
    cd ..
fi

# ========== CONFIGURATION ==========
USER_AGENT="BunkerWebTileDownloader/1.0 (contact@bunkerity.com)"
BASE_URL="https://tile.openstreetmap.org"
MIN_ZOOM=2
MAX_ZOOM=4
OUT_DIR="./src/ui/app/static/img/tiles"
MAX_RETRIES=5
SLEEP_BETWEEN_REQUESTS=0.6   # OSM: no more than 2–3 requests per second

rm -rf "$OUT_DIR"

download_tile() {
    local z="$1"
    local x="$2"
    local y="$3"
    local tile_dir="$OUT_DIR/$z/$x"
    local tile_file="$tile_dir/$y.png"
    local url="$BASE_URL/$z/$x/$y.png"

    # Already downloaded
    [[ -f "$tile_file" ]] && return

    mkdir -p "$tile_dir"

    local attempt=1
    local delay="$SLEEP_BETWEEN_REQUESTS"
    while (( attempt <= MAX_RETRIES )); do
        wget --user-agent="$USER_AGENT" -q -O "$tile_file" "$url" && break
        echo "Failed: $url (attempt $attempt)"
        rm -f "$tile_file"
        sleep "$delay"
        delay=$(awk "BEGIN {print $delay * 2}") # exponential backoff
        ((attempt++))
    done

    if (( attempt > MAX_RETRIES )); then
        echo "Giving up: $url"
    else
        echo "Downloaded: $z/$x/$y.png"
    fi
}

for z in $(seq "$MIN_ZOOM" "$MAX_ZOOM"); do
    max_index=$(( (1 << z) - 1 ))
    for x in $(seq 0 "$max_index"); do
        for y in $(seq 0 "$max_index"); do
            download_tile "$z" "$x" "$y"
            sleep "$SLEEP_BETWEEN_REQUESTS"
        done
    done
done

echo "All tiles downloaded under $OUT_DIR."

# Notes:
# - Set USER_AGENT to your real email/website for OSM compliance.
# - This script never runs more than 1 request at a time.
# - The 0.6s delay is <2 req/sec (safe).
# - If you want to throttle more (e.g. overnight download), increase SLEEP_BETWEEN_REQUESTS.
# - Respect OSM: never mass-download huge areas.
