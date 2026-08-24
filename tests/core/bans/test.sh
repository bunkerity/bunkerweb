#!/bin/bash
# A ban has to outlive the instance that enforces it. Before 1.7 it lived only in each instance's
# `datastore` shared memory zone, so a restart lost it outright -- and an instance that was
# unreachable when an operator revoked a ban came back still enforcing it and re-taught it to the
# whole cluster. 1.7 writes every decision to `bw_bans` first and reconciles the fleet from that
# table with the `sync-bans` job.
#
# That is a property of a container's lifecycle, not of a configuration, so it cannot be expressed
# as `config:` on an action -- the framework restarts the scheduler between actions but never the
# instance. Hence a script.
#
# Two halves, and they need DIFFERENT kinds of unreachable, because they exercise different code:
#
#  * The restore half stops the instance. It comes back with an empty shared dict, and `sync-bans`
#    projects the database onto it (`project_bans`). The worker is stopped across the restart so
#    that the empty dict is *asserted* rather than raced against the once-a-minute job.
#  * The revoke half keeps the instance RUNNING and cuts only the network it shares with the
#    scheduler. It therefore comes back still holding the ban, which is the whole point: the
#    re-unban branch of `sync-bans` (the `tombstoned` loop) only runs when the instance REPORTS a
#    ban the database no longer has. Stopping the container instead empties the dict, the instance
#    reports nothing, and that branch never executes -- the test would then pass with the branch
#    deleted.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "bans supports only the docker integration" >&2
	exit 1
fi

# Overridable so the spec can be proven on an isolated stack without the framework's fixed names.
instance="${BW_TEST_INSTANCE:-bunkerweb}"
scheduler="${BW_TEST_SCHEDULER:-bw-scheduler}"
worker="${BW_TEST_WORKER:-bw-worker}"
api="${BW_TEST_API_URL:-http://127.0.0.1:8888}"
api_auth="${BW_TEST_API_AUTH:-admin:P@ssw0rd}"

ip="10.99.1.1"
needle="\"ip\":\"${ip}\""
# `sync-bans` is scheduled once a minute; allow two windows plus slack before calling it a failure.
converge_timeout=180

# Networks the instance shares with the scheduler, and the aliases it answers to on them. Captured
# before anything is cut so the reconnect restores exactly what compose set up -- a plain
# `docker network connect` would drop the alias the scheduler resolves the instance by.
shared_networks=()
declare -A network_aliases=()

api_get() { curl -sS -u "$api_auth" "${api}$1" || true; }

fail() {
	echo "bans: $*" >&2
	echo "bans: last database view: $(api_get /bans)" >&2
	echo "bans: last instance view: $(api_get /bans/instances)" >&2
	exit 1
}

# `/bans/instances` answers 502 with an error payload whenever an instance is unreachable
# (src/api/app/routers/bans.py), and an error body carries no needle either -- so every absence has
# to be qualified by a well-formed answer or a half-started API reads as "the ban is gone".
well_formed() { case "$1" in *'"status":"success"'*) return 0 ;; esac; return 1; }

wait_healthy() {
	for _ in {1..90}; do
		[ "$(docker inspect --format '{{.State.Health.Status}}' "$instance" 2>/dev/null || true)" = "healthy" ] && return
		sleep 2
	done
	fail "instance $instance did not become healthy"
}

# Polls a view until the needle is present (`want=yes`) or absent (`want=no`).
converge() {
	local path="$1" want="$2" label="$3" deadline=$((SECONDS + converge_timeout)) body
	while [ "$SECONDS" -lt "$deadline" ]; do
		body="$(api_get "$path")"
		if well_formed "$body"; then
			case "$body" in
			*"$needle"*) [ "$want" = "yes" ] && { echo "bans: $label"; return; } ;;
			*) [ "$want" = "no" ] && { echo "bans: $label"; return; } ;;
			esac
		fi
		sleep 3
	done
	fail "$label did not happen within ${converge_timeout}s"
}

assert_view() {
	local path="$1" want="$2" label="$3" body
	body="$(api_get "$path")"
	well_formed "$body" || fail "$label: $path did not answer successfully: $body"
	case "$body" in
	*"$needle"*) [ "$want" = "yes" ] || fail "$label: $needle is in $path and should not be" ;;
	*) [ "$want" = "no" ] || fail "$label: $needle is missing from $path" ;;
	esac
}

capture_shared_networks() {
	local network aliases
	while read -r network; do
		[ -n "$network" ] || continue
		docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$scheduler" |
			grep -qx "$network" || continue
		aliases="$(docker inspect -f "{{range \$name, \$conf := .NetworkSettings.Networks}}{{if eq \$name \"${network}\"}}{{range \$conf.Aliases}}{{.}} {{end}}{{end}}{{end}}" "$instance")"
		shared_networks+=("$network")
		network_aliases["$network"]="$aliases"
	done < <(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$instance")
	[ "${#shared_networks[@]}" -gt 0 ] || fail "no network shared between $instance and $scheduler"
}

cut_scheduler_path() {
	local network
	for network in "${shared_networks[@]}"; do
		docker network disconnect "$network" "$instance" >/dev/null
	done
}

restore_scheduler_path() {
	local network alias args
	for network in "${shared_networks[@]}"; do
		docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$instance" |
			grep -qx "$network" && continue
		args=()
		for alias in ${network_aliases["$network"]}; do
			args+=(--alias "$alias")
		done
		docker network connect "${args[@]}" "$network" "$instance" >/dev/null
	done
}

cleanup() {
	docker start "$worker" >/dev/null 2>&1 || true
	docker start "$instance" >/dev/null 2>&1 || true
	restore_scheduler_path 2>/dev/null || true
	docker exec "$scheduler" bwcli unban "$ip" >/dev/null 2>&1 || true
}
trap cleanup EXIT

capture_shared_networks

# --- restore: the ban is taken while nothing can deliver it ------------------------------------
# The worker is stopped first so `sync-bans` cannot run at all across this half. Without that, the
# job's once-a-minute tick races the assertions below and the empty shared dict -- the thing that
# makes the restore mean something -- can only be hoped for, not asserted.
docker stop "$worker" >/dev/null
docker stop "$instance" >/dev/null
docker exec "$scheduler" bwcli ban "$ip" -exp 3600 -reason "bans-spec" >/dev/null 2>&1 ||
	fail "bwcli ban failed while the instance was down (it must still persist)"
assert_view /bans yes "ban taken with the instance down"

docker start "$instance" >/dev/null
wait_healthy
# The red half, pinned rather than assumed: the restart wiped the shared dict, and with the worker
# down nothing can have refilled it.
assert_view /bans/instances no "the instance came back with an empty shared dict"

docker start "$worker" >/dev/null
# Only `sync-bans` can put it back: the fan-out at ban time had nobody to talk to, and the dict was
# provably empty one line ago.
converge /bans/instances yes "the restarted instance was taught the ban again"
assert_view /bans yes "the database kept the ban across the restart"

# --- revoke: the instance stays up, only the scheduler's path to it is cut ----------------------
cut_scheduler_path
docker exec "$scheduler" bwcli unban "$ip" >/dev/null 2>&1 ||
	fail "bwcli unban failed while the instance was unreachable"
assert_view /bans no "revoke persisted with the instance unreachable"
restore_scheduler_path

# This is the pre-1.7 failure state, and it has to be reached for the rest to mean anything: the
# instance never got the unban and is still enforcing a ban the database no longer has.
assert_view /bans/instances yes "the unreachable instance came back still enforcing the revoked ban"
# `sync-bans` reads that back, sees a ban with no row behind it, and replays the unban to that
# instance. Deleting the branch leaves this hanging until the timeout.
converge /bans/instances no "sync-bans replayed the revoke to the instance that had missed it"
assert_view /bans no "the database still has no row for the revoked ban"

echo "bans: all checks passed"
