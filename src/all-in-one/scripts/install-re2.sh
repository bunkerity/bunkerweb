#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

set_ntask

echo "ℹ️ Cloning and building re2 $VERSION"

echo "ℹ️ Cloning re2 from $URL (commit $COMMIT)"
git_clone_commit re2 "$URL" "$COMMIT"

echo "ℹ️ Installing re2"
make install

echo "✅ re2 $VERSION built successfully"
