#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

echo "ℹ️ Cloning and building CrowdSec $VERSION"

echo "ℹ️ Cloning CrowdSec from $URL (commit $COMMIT)"
git_clone_commit crowdsec "$URL" "$COMMIT"

echo "ℹ️ Building CrowdSec"
make BUILD_VERSION="$VERSION" BUILD_STATIC=1 release

echo "✅ CrowdSec $VERSION built successfully"
