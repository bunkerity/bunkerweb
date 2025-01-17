#!/bin/sh
set -ex
git status | grep -v '#'

NUMBER=$(grep LIBINJECTION_VERSION src/version.h | head -1 | awk '{print $3}' | tr -d '"')
test -z "$NUMBER" && exit 1
VERSION="v${NUMBER}"
git tag -a "$VERSION" -m "$VERSION"
git push origin "$VERSION"



