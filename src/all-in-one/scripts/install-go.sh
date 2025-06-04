#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

echo "ℹ️ Downloading and installing Go $VERSION for $PLATFORM"

echo "ℹ️ Downloading Go from $URL"
wget -O "/tmp/go-${VERSION}-${PLATFORM}.tar.gz" "$URL"

echo "ℹ️ Verifying Go archive checksum"
echo "$SHA256  /tmp/go-${VERSION}-${PLATFORM}.tar.gz" | sha256sum -c - || { echo "SHA256 mismatch with go-${VERSION}-${PLATFORM}.tar.gz" ; exit 1 ; }

echo "ℹ️ Installing Go to /usr/local/go"
rm -rf /usr/local/go
tar -C /usr/local -xzf "/tmp/go-${VERSION}-${PLATFORM}.tar.gz"

echo "✅ Go $VERSION for $PLATFORM installed successfully"
