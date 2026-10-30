#!/bin/bash

# Fetch latest stable and latest non-stable (prerelease) versions for bunkerity/bunkerweb
# - Outputs to stdout via logs
# - Exports BW_LATEST_STABLE and BW_LATEST_NON_STABLE

set -euo pipefail

REPO="${REPO:-bunkerity/bunkerweb}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "ℹ️ Fetching latest stable release …"
stable_tag=$(REPO="$REPO" python3 "$script_dir/latest_stable.py" || true)
if [ -z "$stable_tag" ]; then
  echo "❌ Failed to fetch latest stable release from GitHub"
  exit 1
fi

echo "ℹ️ Fetching latest non-stable (prerelease) …"
non_stable_tag=$(REPO="$REPO" python3 "$script_dir/latest_prerelease.py" || true)
if [ -z "$non_stable_tag" ]; then
  echo "⚠️ No non-stable (prerelease) version found"
fi

BW_LATEST_STABLE="$stable_tag"
export BW_LATEST_STABLE

BW_LATEST_NON_STABLE="$non_stable_tag"
export BW_LATEST_NON_STABLE

echo "ℹ️ Latest stable: $BW_LATEST_STABLE"
echo "ℹ️ Latest non-stable: ${BW_LATEST_NON_STABLE:-<none>}"
