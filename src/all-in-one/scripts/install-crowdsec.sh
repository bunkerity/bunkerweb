#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

echo "ℹ️ Cloning and building CrowdSec $VERSION"

echo "ℹ️ Cloning CrowdSec from $URL (commit $COMMIT)"
git_clone_commit crowdsec "$URL" "$COMMIT"

echo "ℹ️ Patching CrowdSec Go dependencies for CVE fixes"
go get github.com/slack-go/slack@v0.23.1 # GHSA-gxhx-2686-5h9g
go get golang.org/x/crypto@v0.52.0 # CVE-2026-46598 CVE-2026-46597 CVE-2026-46595 CVE-2026-42508 CVE-2026-39835 CVE-2026-39834 CVE-2026-39833 CVE-2026-39832 CVE-2026-39831 CVE-2026-39830 CVE-2026-39829 CVE-2026-39828 CVE-2026-39827
go get golang.org/x/net@v0.55.0 # CVE-2026-42506 CVE-2026-42502 CVE-2026-39821 CVE-2026-27136 CVE-2026-25681 CVE-2026-25680
go get github.com/quic-go/quic-go@v0.59.1 # CVE-2026-40898
go mod tidy

echo "ℹ️ Building CrowdSec"
make clean release BUILD_VERSION="$VERSION" DOCKER_BUILD=1 BUILD_STATIC=1 CGO_CFLAGS="-D_LARGEFILE64_SOURCE"

echo "✅ CrowdSec $VERSION built successfully"
