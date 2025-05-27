#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

set_ntask

echo "ℹ️ Cloning and building abseil-cpp $VERSION"

echo "ℹ️ Fetching abseil-cpp from $URL (commit $COMMIT)"
git_clone_commit abseil-cpp "$URL" "$COMMIT"

echo "ℹ️ Configuring abseil-cpp build"
mkdir build
cd build
cmake -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF ..

echo "ℹ️ Building abseil-cpp"
make -j "$NTASK"

echo "ℹ️ Installing abseil-cpp"
make install

echo "✅ abseil-cpp $VERSION built successfully"
