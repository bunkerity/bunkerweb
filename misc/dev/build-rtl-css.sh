#!/bin/bash
# Regenerate the right-to-left UI stylesheets with rtlcss (dev-time tool, needs node + network, never run in CI or image builds).
# Output: src/ui/app/static/css/rtl/<same relative path>. Each output ends with a trailer line
#   /* rtlcss@<ver> source=<path> sha256=<sha of the LTR source> */
# which tests/unit/ui uses to detect a stale sheet without node.
# css/overrides.css is an @import index over css/overrides/*.css: rtlcss would copy the imports verbatim (and
# css/rtl/overrides/ does not exist), so it reads the merged text (misc/build/merge_css_imports.py --print) and the
# trailer hashes that text. Outputs sit one directory below their sources, so relative url()s get one more "../".
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

# Relative url()s in a css/ source are resolved from css/; the output lives in css/rtl/, so each one needs a "../".
# A libs/ source would need a different prefix: none carries a relative url today, so one appearing is an error.
rebase_urls() { # <source rel> <output file>
    python3 - "$1" "$2" "$ROOT/misc/build" <<'PY'
import sys
from pathlib import Path

source, output, build = sys.argv[1:]
sys.path.insert(0, build)
from merge_css_imports import ABSOLUTE_RE, COMMENT_RE, URL_RE  # noqa: E402

path = Path(output)
chunks = COMMENT_RE.split(path.read_text(encoding="utf-8"))  # odd chunks are comments: left alone


def fix(match):
    quote, url = match.group(1), match.group(2)
    if ABSOLUTE_RE.match(url):
        return match.group(0)
    if not source.startswith("css/"):
        sys.exit(f"build-rtl-css: {source} has a relative url({url}); teach rebase_urls() its prefix")
    return f"url({quote}../{url}{quote})"


path.write_text("".join(c if i % 2 else URL_RE.sub(fix, c) for i, c in enumerate(chunks)), encoding="utf-8")
PY
}

generate() { # <source rel> <dest file>
    src="$STATIC/$1"
    case "$1" in
    css/overrides.css)
        src="$(mktemp --suffix=.css)"
        python3 "$ROOT/misc/build/merge_css_imports.py" --print "$STATIC/$1" >"$src"
        ;;
    esac
    mkdir -p "$(dirname "$2")"
    npx --yes "rtlcss@$RTLCSS_VERSION" -s "$src" "$2" 2>/dev/null
    rebase_urls "$1" "$2"
    printf '\n/* rtlcss@%s source=%s sha256=%s */\n' "$RTLCSS_VERSION" "$1" "$(sha256sum "$src" | cut -d' ' -f1)" >>"$2"
    [ "$src" = "$STATIC/$1" ] || rm -f "$src"
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
