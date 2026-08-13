#!/bin/bash

# Self-check for example_hook: it runs an example's own setup/cleanup script from inside
# the stack directory, and it stays quiet when the example ships none. The happy path
# only ever runs in CI, where sudo needs no password, so check it here instead.

# utils.sh takes the integration as its first argument and refuses to load without one.
# shellcheck disable=SC1091
source tests/scripts/utils.sh Docker core

tmp_dir="$(mktemp -d)"
marker_backup=""
if [ -f /tmp/example_stack.txt ] ; then
    marker_backup="$(mktemp)"
    cp /tmp/example_stack.txt "$marker_backup"
fi

cleanup() {
    rm -rf "$tmp_dir"
    if [ -n "$marker_backup" ] ; then
        mv "$marker_backup" /tmp/example_stack.txt
    else
        rm -f /tmp/example_stack.txt
    fi
}
trap cleanup EXIT

echo "$tmp_dir/docker-compose.yml" > /tmp/example_stack.txt
printf '#!/bin/bash\npwd > ./ran.txt\n' > "$tmp_dir/setup-docker.sh"

failures=0

if ! example_hook setup Docker ; then
    echo "❌ example_hook reported a failure on a script that succeeds"
    failures=$((failures+1))
elif [ "$(cat "$tmp_dir/ran.txt" 2>/dev/null)" != "$tmp_dir" ] ; then
    echo "❌ setup-docker.sh did not run from the stack directory"
    failures=$((failures+1))
fi

# An integration the example does not ship a script for is not an error.
if ! example_hook setup Kubernetes ; then
    echo "❌ example_hook failed on a missing script instead of skipping it"
    failures=$((failures+1))
fi

printf '#!/bin/bash\nexit 3\n' > "$tmp_dir/cleanup-docker.sh"
if example_hook cleanup Docker ; then
    echo "❌ example_hook swallowed a failing script"
    failures=$((failures+1))
fi

if [ $failures -eq 0 ] ; then
    echo "✅ example_hook self-check passed"
fi
exit $failures
