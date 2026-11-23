#!/bin/bash
# Custom config type directory that the instance user cannot write to (1.6.18 regression).
#
# On Linux and All-in-one the scheduler pushes /etc/bunkerweb/configs onto the very same path. The
# instance swaps every top-level entry of the push in through a rename: it parks the existing entry,
# places the staged one, drops the parked copy. A type directory owned root:nginx with mode 750
# cannot be renamed by the nginx user, so the instance answered 500 `cannot park server-http: ...
# Permission denied` and, since 1.6.18, the reload was held back forever. The entry did not even
# change: the push carried the very bytes already on disk. pushswap.lua no longer parks an entry that
# equals its staged copy.
#
# Usage: test.sh <container> <aio|linux> [host]
#   1. as root inside the container: put a `location = /cfgperm` probe in server-http, hand the
#      directory to root:nginx 750 and the file to 640 (what a hardened install or an operator's
#      chown -R leaves behind);
#   2. ask the scheduler to rescan (SIGHUP), which regenerates and pushes the configs;
#   3. wait for the probe to answer from inside the container, then check the scheduler never logged
#      `cannot park`.
# The runner asserts the probe from the outside in the next action.

CONTAINER="${1:?container name}"
MODE="${2:?aio or linux}"
HOST="${3:-www.example.com}"
TYPE_DIR="/etc/bunkerweb/configs/server-http"
TIMEOUT=180

fail() {
    echo "custom_config_dir_without_group_write: FAIL: $*"
    exit 1
}

dx() { docker exec -u 0 "$CONTAINER" "$@"; }

started="$(date +%s)"

dx sh -c "mkdir -p $TYPE_DIR && printf 'location = /cfgperm {\n    default_type text/plain;\n    return 200 \"cfgperm-probe-ok\";\n}\n' > $TYPE_DIR/cfgperm.conf" || fail "cannot write the probe"
dx sh -c "chown -R root:nginx $TYPE_DIR && chmod 750 $TYPE_DIR && chmod 640 $TYPE_DIR/cfgperm.conf" || fail "cannot change owner and mode"

state="$(dx stat -c '%U:%G %a' "$TYPE_DIR")"
file_state="$(dx stat -c '%U:%G %a' "$TYPE_DIR/cfgperm.conf")"
[ "$state" == "root:nginx 750" ] || fail "directory is '$state', expected 'root:nginx 750'"
[ "$file_state" == "root:nginx 640" ] || fail "file is '$file_state', expected 'root:nginx 640'"
echo "custom_config_dir_without_group_write: $TYPE_DIR is $state, probe file is $file_state"

if [ "$MODE" == "linux" ]; then
    # ExecReload sends SIGHUP to the scheduler (src/linux/scripts/bunkerweb-scheduler.sh)
    dx systemctl reload bunkerweb-scheduler.service || fail "cannot signal the scheduler"
else
    # the pattern is anchored so the wrapper scripts, whose command line also names the path, do not match
    # shellcheck disable=SC2016 # the substitution has to run inside the container
    dx sh -c 'kill -HUP $(pgrep -f "^python3 /usr/share/bunkerweb/scheduler/main.py")' || fail "cannot signal the scheduler"
fi

deadline=$((SECONDS + TIMEOUT))
body=""
while [ $SECONDS -lt $deadline ]; do
    body="$(dx curl -s -m 5 -H "Host: $HOST" http://127.0.0.1/cfgperm 2> /dev/null)"
    if [ "$body" == "cfgperm-probe-ok" ]; then
        break
    fi
    sleep 3
done
[ "$body" == "cfgperm-probe-ok" ] || fail "the probe did not answer within ${TIMEOUT}s (got '${body:0:60}')"

if [ "$MODE" == "linux" ]; then
    logs="$(dx sh -c 'cat /var/log/bunkerweb/scheduler.log 2> /dev/null')"
else
    logs="$(docker logs --since "$started" "$CONTAINER" 2>&1)"
fi
if grep -q "cannot park" <<< "$logs"; then
    grep "cannot park" <<< "$logs" | head -3
    fail "the instance refused the push: cannot park"
fi

state_after="$(dx stat -c '%U:%G %a' "$TYPE_DIR")"
[ "$state_after" == "root:nginx 750" ] || fail "directory became '$state_after' after the push"

echo "custom_config_dir_without_group_write: all checks passed"
