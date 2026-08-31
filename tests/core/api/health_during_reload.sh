#!/bin/bash
# `/health` is not a value a fresh instance answers once and forgets: `POST /reload`
# (src/bw/lua/bunkerweb/api.lua) writes /var/tmp/bunkerweb_reloading BEFORE signalling nginx and
# only removes it once the NEW worker generation has finished init_by_lua
# (src/common/confs/init-worker-lua.conf), so the marker's lifetime spans the whole reload, not
# just the HUP signal. Racing a background reload against a tight `/health` poll loop is the only
# way to observe that window from outside: the framework's own actions run strictly sequentially,
# so nothing expressible as ordinary YAML actions could ever land between "signal sent" and "new
# worker up" on the same instance.
#
# Docker only: fixed loopback port, no arm-specific API port juggling (tests/core/api.yml hardcodes
# the same 127.0.0.1:5001 for every action regardless of arm; only Linux and All-in-one differ, and
# they are out of scope here).
set -Eeuo pipefail

api="http://127.0.0.1:5001"
host="bwapi"
token="tests-secret-token"

curl_api() {
	local timeout="$1"
	shift
	curl -sS -m "$timeout" -H "Host: $host" -H "Authorization: Bearer $token" "$@"
}

fail() {
	echo "health_during_reload: $*" >&2
	exit 1
}

reload_response_file="$(mktemp)"
trap 'rm -f "$reload_response_file"' EXIT

# Confirm the instance is settled ("ok") before racing anything -- a poll loop that only ever saw
# "loading" or "needs_config" from a stack that never finished its first config push would pass
# for the wrong reason.
before="$(curl_api 5 "$api/health")"
case "$before" in
*'"msg":"ok"'*) ;;
*) fail "instance was not settled (msg:ok) before the reload, got: $before" ;;
esac

# A dedicated 60s timeout, not the polls' 5s: the worst non-pathological reload path (SWAP_WAIT
# 30s lock + two `nginx -t` + confirm_reload's 2s) is ~6s, but sharing the polls' -m 5 turned any
# slower box into a `curl: (28)` in the response file and a false "the reload did not itself
# succeed" red.
curl_api 60 -X POST "$api/reload" >"$reload_response_file" 2>&1 &
reload_pid=$!

seen_reloading=0
# ~400 polls; each curl invocation costs several ms on its own, so this comfortably spans the
# window without a fixed sleep dominating it. Not a fixed wall-clock budget on purpose: the
# window this races is server-side and this loop's only job is to sample it as densely as it can
# until the reload it is racing finishes.
for _ in $(seq 1 400); do
	if ! kill -0 "$reload_pid" 2>/dev/null; then
		break
	fi
	body="$(curl_api 5 "$api/health" || true)"
	case "$body" in
	*'"msg":"reloading"'*)
		seen_reloading=1
		break
		;;
	esac
done

wait "$reload_pid" || true
reload_response="$(cat "$reload_response_file" 2>/dev/null || true)"

case "$reload_response" in
*'"msg":"reload successful"'*) ;;
*) fail "the reload this raced against did not itself succeed, got: $reload_response" ;;
esac

# `/reload`'s own HTTP response only proves nginx picked the new configuration up
# (`confirm_reload()` returns once the old worker generation has exited); the marker itself is
# cleared by init-worker-lua.conf's `ready_work`, which the new worker schedules on a
# `timer_at(5, ...)` rather than running inline -- so "ok" can legitimately still be a few
# seconds away here. A bounded poll is the correct read of that, not a race against a slow CI
# box: 30 x 1s comfortably clears the 5s timer with margin.
after=""
settled=0
for _ in $(seq 1 30); do
	after="$(curl_api 5 "$api/health" || true)"
	case "$after" in
	*'"msg":"ok"'*)
		settled=1
		break
		;;
	*'"msg":"reloading"'*)
		# The settle loop can be the only place that catches the marker's 5s tail
		# (`timer_at(5, ready_work)`'s removal of it) if the poll loop above broke on the
		# reload PID exiting before it ever sampled "reloading" itself.
		seen_reloading=1
		;;
	esac
	sleep 1
done
[ "$settled" -eq 1 ] || fail "instance did not settle back to msg:ok within 30s after the reload, last read: $after"

[ "$seen_reloading" -eq 1 ] || fail "never observed msg:reloading while racing a real reload"

echo "health_during_reload: reloading was observed"
