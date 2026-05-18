#!/bin/bash

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "$0")/utils.sh"

echo "ℹ️ Cloning and building CrowdSec $VERSION"

echo "ℹ️ Cloning CrowdSec from $URL (commit $COMMIT)"
git_clone_commit crowdsec "$URL" "$COMMIT"

echo "ℹ️ Patching CrowdSec Go dependencies for CVE fixes"
go get go.opentelemetry.io/otel@v1.41.0                             # CVE-2026-29181
go get github.com/aws/aws-sdk-go-v2/service/cloudwatchlogs@v1.65.0  # GHSA-xmrv-pmrh-hhx2
go get github.com/aws/aws-sdk-go-v2/service/kinesis@v1.43.5         # GHSA-xmrv-pmrh-hhx2
go get github.com/aws/aws-sdk-go-v2/service/s3@v1.97.3              # GHSA-xmrv-pmrh-hhx2
go get github.com/aws/aws-sdk-go-v2/aws/protocol/eventstream@v1.7.8 # GHSA-xmrv-pmrh-hhx2
go get golang.org/x/net@v0.53.0 # CVE-2026-33814
go mod tidy

echo "ℹ️ Building CrowdSec"
make clean release BUILD_VERSION="$VERSION" DOCKER_BUILD=1 BUILD_STATIC=1 CGO_CFLAGS="-D_LARGEFILE64_SOURCE"

echo "✅ CrowdSec $VERSION built successfully"
