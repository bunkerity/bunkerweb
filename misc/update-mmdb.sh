#!/bin/bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/.." && pwd -P)"
temp_root="$(mktemp -d "${TMPDIR:-/tmp}/bunkerweb-mmdb.XXXXXX")"

cleanup() {
    rm -rf -- "$temp_root"
}

trap cleanup EXIT

python3 "$script_dir/update-mmdb.py" --repo-root "$repo_root" --temp-root "$temp_root"
