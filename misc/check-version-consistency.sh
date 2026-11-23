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

# --- 1. Anchored pins. Each captured value must equal VERSION. ---
check_pin() {
    local file="$1" pattern="$2" found
    found="$(sed -nE "s/$pattern/\\1/p" "$file" 2>/dev/null | head -1 || true)"
    if [ -z "$found" ]; then
        note "$file: expected a version pin matching /$pattern/, found none"
    elif [[ "$found" != "$VERSION" ]]; then
        note "$file: pin is '$found', expected $VERSION"
    fi
}

echo "Checking version pins against src/VERSION ($VERSION)"
for df in src/*/Dockerfile; do
    check_pin "$df" '.*LABEL version="([^"]*)".*'
done
check_pin misc/install-bunkerweb.sh '^DEFAULT_BUNKERWEB_VERSION="([^"]*)".*'
check_pin publiccode.yml '^softwareVersion: (.*)'
check_pin pyproject.toml '^version = "([^"]*)".*'
check_pin .github/ISSUE_TEMPLATE/bug_report.yml '^      value: (1\.[0-9][^ ]*).*'

# --- 2. No stale literal from the current release line. ---
# Historical references to older lines (1.5.9, 1.6.5, 1.6.0-beta) are legitimate.
# These paths also carry intentional references to the current release line:
#   CHANGELOG.md                      released history
#   src/common/db/alembic/            revision ids and down_revision chains
#   .github/RELEASING.md              worked examples of the tag convention
#   misc/install-bunkerweb.sh         ~rc vs -rc comparison examples in comments
#   docs/{<locale>/}features.md       version bounds in generated prose
CORE="${VERSION%%[~-]*}"
mapfile -t stale < <(
    git grep -nE "${CORE//./\\.}[~-]rc[0-9]+" -- \
        ':!CHANGELOG.md' \
        ':!src/common/db/alembic/**' \
        ':!.github/RELEASING.md' \
        ':!.github/scripts/**' \
        ':!docs/superpowers/**' \
        ':!misc/install-bunkerweb.sh' \
        ':!misc/check-version-consistency.sh' 2>/dev/null |
        grep -vE '^(\.github/workflows/release\.yml:[0-9]+:\ \ \ \ \ \ \ \ \ \ \#\ '\`'sort\ \-V'\`'\ puts\ 1\.6\.18\-rc4\ after\ 1\.6\.18,\ so\ '\`'\-rc'\`'\ is\ mapped\ to\ '\`'\~rc'\`'\ \(sorts\ first\)\ and\ back\.|tests/unit/common/test_version_consistency\.py:[0-9]+:@pytest\.mark\.parametrize\("stale",\ \[VERSION\ \+\ "0",\ VERSION\.replace\("\~",\ "\-"\)\ \+\ "0",\ "1\.6\.18\~rc3",\ VERSION\ \+\ "\-extra"\]\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ \ \ \ \ host\.ok\("afterRemoveDEB\.sh",\ "upgrade",\ "1\.6\.18\~rc4",\ original=old_revision\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ \ \ \ \ host\.ok\("beforeRemove\.sh",\ "upgrade",\ "1\.6\.18\~rc4"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ host\.ok\("beforeInstall\.sh",\ \*\(\("2",\)\ if\ rpm\ else\ \("upgrade",\ "1\.6\.18\~rc4"\)\)\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ host\.ok\("postinstall\.sh",\ \*\(\("1",\)\ if\ rpm\ else\ \("configure",\ "1\.6\.18\~rc4"\)\)\)|tests/unit/linux/test_lxq_migration_config\.py:[0-9]+:\ \ \ \ \(directory\.parent\.parent\ /\ "VERSION"\)\.write_text\("1\.6\.18\~rc4"\)|tests/unit/linux/test_lxq_repository_bootstrap\.py:[0-9]+:\ \ \ \ \ \ \ \ BUNKERWEB_VERSION='\''1\.6\.18\~rc4'\''|tests/unit/gen/test_save_config_cli_outcomes\.py:[0-9]+:\ \ \ \ \ \ \ \ \("1\.6\.17",\ "1\.6\.18\~rc3",\ "sqlite",\ True\),|tests/unit/gen/test_save_config_cli_outcomes\.py:[0-9]+:\ \ \ \ \ \ \ \ \("1\.6\.17",\ "1\.6\.18\~rc3",\ "postgresql",\ False\),|tests/unit/gen/test_save_config_cli_outcomes\.py:[0-9]+:\ \ \ \ \ \ \ \ \("1\.6\.17",\ "1\.6\.18\-rc3",\ "sqlite",\ True\),|tests/unit/gen/test_save_config_cli_outcomes\.py:[0-9]+:\ \ \ \ \(tmp_path\ /\ "sqlite_versions/abc_upgrade_to_version_1_6_18_rc3\.py"\)\.touch\(\)|tests/unit/common/test_system_utility_outcomes\.py:[0-9]+:\ \ \ \ version\.write_text\("1\.6\.18\~rc3\\n"\)|tests/unit/common/test_system_utility_outcomes\.py:[0-9]+:\ \ \ \ assert\ utils\.get_version\(\)\ ==\ "1\.6\.18\~rc3"|tests/unit/common/test_system_utility_outcomes\.py:[0-9]+:\ \ \ \ assert\ utils\.is_newer_version_available\("v1\.6\.18\~rc3",\ "1\.6\.18"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ \(root\ /\ "usr/share/bunkerweb/VERSION"\)\.write_text\("1\.6\.18\~rc3\\n"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ host\.ok\("beforeInstall\.sh",\ \*\(\("2",\)\ if\ rpm\ else\ \("upgrade",\ "1\.6\.18\~rc3"\)\)\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:@pytest\.mark\.parametrize\("old_revision",\ \["v1\.6\.18\-rc3",\ "3a9c1381f84f248cbb6c5210d22bafebdf0ab941"\]\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ host\.ok\("beforeInstall\.sh",\ \*\(\("2",\)\ if\ rpm\ else\ \("upgrade",\ "1\.6\.18\~rc3"\)\)\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ \ \ \ \ host\.ok\("postinstall\.sh",\ \*\(\("1",\)\ if\ rpm\ else\ \("configure",\ "1\.6\.18\~rc3"\)\)\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ result\ =\ host\.run\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("beforeInstall\.sh",\ "upgrade",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ result\ =\ host\.run\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ result\ =\ host\.run\("beforeInstall\.sh",\ "upgrade",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("beforeInstall\.sh",\ "upgrade",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("beforeInstall\.sh",\ "upgrade",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3",\ SERVICE_API="no"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("beforeInstall\.sh",\ \*\(\("2",\)\ if\ rpm\ else\ \("upgrade",\ "1\.6\.18\~rc3"\)\)\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ \*\(\("1",\)\ if\ rpm\ else\ \("configure",\ "1\.6\.18\~rc3"\)\),\ \*\*\{setting:\ "no"\}\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("beforeInstall\.sh",\ "upgrade",\ "1\.6\.18\~rc3"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ result\ =\ host\.run\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3",\ FAIL_RESTART="bunkerweb\-ui"\)|tests/unit/linux/test_lxp_package_lifecycle\.py:[0-9]+:\ \ \ \ host\.ok\("postinstall\.sh",\ "configure",\ "1\.6\.18\~rc3"\))$' |
        awk -v token="${CORE//./[.]}[~-]rc[[:alnum:].~+-]+" -v version="$VERSION" -v tag_version="$TAG_VERSION" '
            {
                rest = $0
                features = sub(/^docs\/([a-z][a-z]\/)?features[.]md:[0-9]+:/, "", rest)
                while (match(rest, token)) {
                    prefix = substr(rest, 1, RSTART - 1)
                    literal = substr(rest, RSTART, RLENGTH)
                    rest = substr(rest, RSTART + RLENGTH)
                    if (literal == version || literal == tag_version) continue
                    # A version bound excuses only its own token, even on a line with other pins.
                    if (features && literal ~ /~rc[0-9]+[.]?$/ && prefix ~ /(^|[[:space:](])before $/ && rest ~ /^([[:space:],);!?|]|$)/) continue
                    if (features && literal ~ /~rc[0-9]+$/ && prefix ~ /(^|[[:space:](])$/ && rest ~ /^ or later([[:space:].,);!?|]|$)/) continue
                    print
                    break
                }
            }
        ' || true
)
if [ ${#stale[@]} -gt 0 ]; then
    echo "Stale ${CORE} literals (expected $VERSION or $TAG_VERSION):"
    # Slice rather than piping to head: under `set -o pipefail` a closed pipe
    # turns the whole script's exit into 141 (SIGPIPE) instead of our own 1.
    printf '  %s\n' "${stale[@]:0:20}"
    [ ${#stale[@]} -gt 20 ] && echo "  ... and $(( ${#stale[@]} - 20 )) more"
    fail=1
fi

# --- 3. NGINX: every Linux package must build its modules against the tree it runs. ---
# nginx refuses a dynamic module compiled for another version at config load, so each
# src/linux/Dockerfile-* NGINX_VERSION must match the vendored tree that src/deps/install.sh
# selects for it. Run the installer's case block with each Dockerfile's OS and OS_VERSION,
# then map its build-time path to the corresponding vendored tree in the checkout.
nginx_tree_version() {
    [ -f "$1/src/core/nginx.h" ] || return 0
    sed -n 's/^#define NGINX_VERSION[[:space:]]*"\([^"]*\)"/\1/p' "$1/src/core/nginx.h"
}
read_docker_env() {
    python3 - "$1" "$2" <<'PY'
import re
import shlex
import sys


def logical_lines(dockerfile):
    fragments = []
    in_directives = True
    for raw_line in dockerfile:
        stripped = raw_line.strip()
        if in_directives:
            directive = re.match(r"#\s*(syntax|escape|check)\s*=", stripped, re.IGNORECASE)
            if directive and directive[1].lower() == "escape":
                raise ValueError("# escape= parser directives are unsupported")
            in_directives = directive is not None
        if not stripped or stripped.startswith("#"):
            continue
        line = raw_line.rstrip("\n") if fragments else raw_line.lstrip().rstrip("\n")
        end = line.rstrip(" \t")
        if (len(end) - len(end.rstrip("\\"))) % 2:
            fragments.append(end[:-1])
            continue
        fragments.append(line)
        yield "".join(fragments)
        fragments.clear()
    if fragments:
        yield "".join(fragments)


file, key = sys.argv[1:]
mentions_key = re.compile(rf"\b{re.escape(key)}\b")
value = None
try:
    with open(file, encoding="utf-8-sig") as dockerfile:
        for line in logical_lines(dockerfile):
            instruction = line.split(None, 1)
            if len(instruction) != 2 or instruction[0].lower() != "env":
                continue
            args = instruction[1]
            try:
                tokens = shlex.split(args, posix=True)
            except ValueError:
                if mentions_key.search(args):
                    raise
                continue
            if "=" not in tokens[0]:
                if tokens[0] == key:
                    raise ValueError("legacy ENV syntax")
                continue
            assignments = [token.partition("=") for token in tokens]
            if any(not separator for _, separator, _ in assignments):
                if mentions_key.search(args) or any(name == key for name, _, _ in assignments):
                    raise ValueError("expected KEY=value for every assignment")
                continue
            for name, _, candidate in assignments:
                if name != key:
                    continue
                if value is not None or not candidate or re.search(r"""[\s$"'\\]""", candidate):
                    raise ValueError("expected one non-empty literal value")
                value = candidate
except (OSError, ValueError) as error:
    sys.exit(f"  {file}: unsupported ENV declaration for {key} ({error})")

if value is not None:
    print(value)
PY
}
# A tree without the vendored sources (the release unit test's fixture) has nothing to check.
if [ -d src/deps/src ]; then
    if ! nginx_selector="$(sed -n '/^case "[$]OS:[$]OS_VERSION" in$/,/^esac$/p' src/deps/install.sh)" || [ -z "$nginx_selector" ]; then
        note "src/deps/install.sh: NGINX selector block is missing or unreadable"
    else
        for df in src/linux/Dockerfile-*; do
            [ -f "$df" ] || continue
            if ! pin="$(read_docker_env "$df" NGINX_VERSION)" ||
                ! os="$(read_docker_env "$df" OS)" ||
                ! os_version="$(read_docker_env "$df" OS_VERSION)"; then
                fail=1
                continue
            fi
            [ -z "$pin" ] && continue
            if ! source_dir="$(bash -euc '
                OS=$1 OS_VERSION=$2 NGINX_SRC_DIR=
                eval "$3"
                printf "%s\n" "$NGINX_SRC_DIR"
            ' bash "$os" "$os_version" "$nginx_selector")"; then
                note "$df: could not evaluate the NGINX selector in src/deps/install.sh"
                continue
            fi
            if [ -z "$source_dir" ]; then
                note "$df: NGINX_SRC_DIR is empty for OS=$os OS_VERSION=$os_version"
                continue
            fi
            tree="${source_dir#/tmp/bunkerweb/deps/src/}"
            if [ "$tree" = "$source_dir" ] || [ ! -d "src/deps/src/$tree" ]; then
                note "$df: src/deps/install.sh selects missing vendored NGINX tree '$source_dir'"
                continue
            fi
            selected="$(nginx_tree_version "src/deps/src/$tree")"
            if [ "$selected" != "$pin" ]; then
                note "$df: NGINX_VERSION=$pin but src/deps/install.sh selects $tree (${selected:-no version}) for OS=$os OS_VERSION=$os_version"
            fi
        done
    fi
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
