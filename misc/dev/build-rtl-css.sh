#!/bin/bash
# Regenerate the right-to-left UI stylesheets with rtlcss (dev-time tool, needs node + network, never run in CI or image builds).
# Output: src/ui/app/static/css/rtl/<same relative path>. Each output ends with a trailer line
#   /* rtlcss@<ver> source=<path> sha256=<sha of the LTR source> */
# which tests/unit/ui uses to detect a stale sheet without node.
# Usage: misc/dev/build-rtl-css.sh [--check]   (--check: regenerate to a temp dir, compare, write nothing)
set -eu

RTLCSS_VERSION="4.3.0"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATIC="$ROOT/src/ui/app/static"
OUT="$STATIC/css/rtl"

# source (relative to static/) -> output (relative to css/rtl/). workflow_editor is deliberately absent: the canvas stays LTR.
SOURCES="css/core.css css/theme-default.css css/overrides.css
css/pages/auth-legacy.css css/pages/cache.css css/pages/crowdsec.css css/pages/groups.css css/pages/home.css
css/pages/login.css css/pages/logs.css css/pages/web-cache.css
libs/datatables/datatables.min.css"

out_path() {
    case "$1" in
    css/*) echo "$OUT/${1#css/}" ;;
    libs/*) echo "$OUT/$1" ;;
    esac
}

generate() { # <source rel> <dest file>
    mkdir -p "$(dirname "$2")"
    npx --yes "rtlcss@$RTLCSS_VERSION" -s "$STATIC/$1" "$2" 2>/dev/null
    printf '\n/* rtlcss@%s source=%s sha256=%s */\n' "$RTLCSS_VERSION" "$1" "$(sha256sum "$STATIC/$1" | cut -d' ' -f1)" >>"$2"
    # Same formatter the pre-commit hook runs (needs `prettier` on PATH), so the committed file is already stable under it.
    # `*.min*` is in .prettierignore, so the hook leaves those sources' output alone.
    case "$1" in *.min.*) ;; *) prettier --write "$2" >/dev/null ;; esac
}

if [ "${1:-}" = "--check" ]; then
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    rc=0
    for s in $SOURCES; do
        generate "$s" "$tmp/out.css"
        cmp -s "$tmp/out.css" "$(out_path "$s")" || {
            echo "stale: $s"
            rc=1
        }
    done
    exit $rc
fi

for s in $SOURCES; do
    generate "$s" "$(out_path "$s")"
done
