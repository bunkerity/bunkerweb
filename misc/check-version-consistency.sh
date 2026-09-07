#!/usr/bin/env bash
# Fail if any version pin in the tree disagrees with src/VERSION.
#
# misc/update-version.sh cannot repair a tree it has already passed over: it reads
# OLD_VERSION from src/VERSION, so once that file moves, every chained-literal sed
# matches nothing. A bump done by hand therefore leaves the rest of the tree stale,
# and the release path never notices: container-build.yml runs update-version.sh
# only for testing/dev builds, and release.yml checks the tag against src/VERSION
# and nothing else. This asserts the invariant those two miss.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
VERSION="$(tr -d '\n' < src/VERSION)"
TAG_VERSION="${VERSION//\~/-}"
fail=0

note() {
    printf '  %s\n' "$1"
    fail=1
}

# --- 1. Anchored pins. Each of these is a single line that must carry VERSION. ---
check_pin() {
    local file="$1" pattern="$2" found
    found="$(grep -oE "$pattern" "$file" 2>/dev/null | head -1 || true)"
    if [ -z "$found" ]; then
        note "$file: expected a version pin matching /$pattern/, found none"
    elif [[ "$found" != *"$VERSION"* ]]; then
        note "$file: pin is '$found', expected $VERSION"
    fi
}

echo "Checking version pins against src/VERSION ($VERSION)"
for df in src/*/Dockerfile; do
    check_pin "$df" 'LABEL version="[^"]*"'
done
check_pin misc/install-bunkerweb.sh '^DEFAULT_BUNKERWEB_VERSION="[^"]*"'
check_pin publiccode.yml '^softwareVersion: .*'
check_pin pyproject.toml '^version = "[^"]*"'
check_pin .github/ISSUE_TEMPLATE/bug_report.yml '^      value: 1\.[0-9][^ ]*'

# --- 2. No stale literal from the current release line. ---
# Historical references to older lines (1.5.9, 1.6.5, 1.6.0-beta) are legitimate;
# a leftover from *this* line is always rot. These paths carry it on purpose:
#   CHANGELOG.md                      released history
#   src/common/db/alembic/            revision ids and down_revision chains
#   .github/RELEASING.md              worked examples of the tag convention
#   misc/install-bunkerweb.sh         ~rc vs -rc comparison examples in comments
#   tests/unit/test_installer_versions.sh   version-parsing fixtures
CORE="${VERSION%%[~-]*}"
mapfile -t stale < <(
    git grep -nE "${CORE//./\\.}[~-]rc[0-9]+" -- \
        ':!CHANGELOG.md' \
        ':!src/common/db/alembic/**' \
        ':!.github/RELEASING.md' \
        ':!.github/scripts/**' \
        ':!docs/superpowers/**' \
        ':!misc/install-bunkerweb.sh' \
        ':!tests/unit/test_installer_versions.sh' \
        ':!misc/check-version-consistency.sh' 2>/dev/null |
        grep -vF "$VERSION" | grep -vF "$TAG_VERSION" || true
)
if [ ${#stale[@]} -gt 0 ]; then
    echo "Stale ${CORE} literals (expected $VERSION or $TAG_VERSION):"
    # Slice rather than piping to head: under `set -o pipefail` a closed pipe
    # turns the whole script's exit into 141 (SIGPIPE) instead of our own 1.
    printf '  %s\n' "${stale[@]:0:20}"
    [ ${#stale[@]} -gt 20 ] && echo "  ... and $(( ${#stale[@]} - 20 )) more"
    fail=1
fi

if [ "$fail" -ne 0 ]; then
    cat >&2 <<EOF

Version pins disagree with src/VERSION.
Repair with the previous version passed explicitly, since update-version.sh
reads OLD from src/VERSION and would otherwise no-op:

    bash misc/update-version.sh $VERSION <previous-version>

EOF
    exit 1
fi

echo "All version pins agree with $VERSION"
