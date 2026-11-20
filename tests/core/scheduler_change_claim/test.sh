#!/bin/bash
# Scheduler change claim: a configuration write that lands while the once-jobs of the previous write
# are still running must get its own job cycle. Before `2334ba5b8` the scheduler acknowledged every
# pending change at the END of a cycle, so the second write was rendered by NGINX but its jobs never
# ran: a CrowdSec service created mid-cycle never got its crowdsec.conf, and disabling CrowdSec
# mid-cycle kept the stale one.
#
# The `slowjob` plugin next to this file holds a once-job open for 25 s (it runs whenever a service's
# SLOWJOB_TAG changes), which makes the window wide. Both writes go through the standalone API, so
# the script starts one on the stack's own database: a `core` run does not start it.
#
# Phase 1: create s1 (the slow job runs), then create s2 while it runs. s2 must get its crowdsec.conf.
# Phase 2: touch s1 (the slow job runs), then disable CrowdSec on s2 while it runs. The file must go.
# Phase 1 checks the file in the scheduler cache and in the instance's, which the scheduler pushes.
# Phase 2 checks the scheduler cache only: crowdsec-conf deletes the stale file and exits 0, and
# `once_jobs_republish` (src/scheduler/main.py) skips the push when no once-job reported a change, so
# the instance keeps the stale copy until the next push. That is a separate defect from the claim.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "scheduler_change_claim supports only the docker integration" >&2
	exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
scheduler="${BW_TEST_SCHEDULER:-bw-scheduler}"
instance="${BW_TEST_INSTANCE:-bunkerweb}"
api_name="bw-claim-api"
converge_timeout=180

cleanup() { docker rm -f "$api_name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() {
	echo "scheduler_change_claim: $*" >&2
	docker logs "$scheduler" 2>&1 | grep -E 'slow job|CrowdSec configuration|config changed|Plugins config' | tail -30 >&2 || true
	exit 1
}

sched_env() { docker exec "$scheduler" printenv "$1"; }

slow_starts() { docker logs "$scheduler" 2>&1 | grep -c 'slow job start' || true; }
slow_ends() { docker logs "$scheduler" 2>&1 | grep -c 'slow job end' || true; }

# 1. Install the plugin where the scheduler loads external plugins from, then restart it so it is
#    registered. The slow job also runs once at that boot: wait for it to finish, so no run of it
#    is in flight when the baseline is taken.
docker exec -u 0 "$scheduler" rm -rf /etc/bunkerweb/plugins/slowjob
docker cp "${here}/slowjob" "${scheduler}:/etc/bunkerweb/plugins/slowjob"
docker restart "$scheduler" >/dev/null

deadline=$((SECONDS + 300))
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$scheduler")" = "healthy" ] && [ "$(slow_starts)" -ge 1 ] && [ "$(slow_starts)" -eq "$(slow_ends)" ]; do
	[ "$SECONDS" -lt "$deadline" ] || fail "the scheduler never settled with the slowjob plugin loaded"
	sleep 2
done
sleep 10

# 2. The standalone API on the stack's own database and network.
api_image="$(docker inspect -f '{{.Config.Image}}' "$scheduler" | sed 's#bunkerweb-scheduler#bunkerweb-api#')"
token="$(sched_env API_TOKEN)"
docker rm -f "$api_name" >/dev/null 2>&1 || true
docker run -d --name "$api_name" --memory 1g --network bw-universe -v bw-storage:/data \
	-e "API_TOKEN=${token}" -e "DATABASE_URI=$(sched_env DATABASE_URI)" -e API_WHITELIST_ENABLED=no "$api_image" >/dev/null
api_ip="$(docker inspect -f '{{(index .NetworkSettings.Networks "bw-universe").IPAddress}}' "$api_name")"

# Prints the HTTP status. 000 while the API still boots.
api() { curl -s -o /dev/null -w '%{http_code}' -X "$1" -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' "http://${api_ip}:8888$2" ${3:+-d "$3"} || true; }

deadline=$((SECONDS + 120))
until [ "$(api GET /services)" = "200" ]; do
	[ "$SECONDS" -lt "$deadline" ] || fail "the API never answered 200 on /services"
	sleep 2
done

# The scheduler cache and the instance's, as "<scheduler> <instance>". Read in the containers: the
# runner has no view of either.
conf_state() {
	local out="" c
	for c in "$scheduler" "$instance"; do
		out+="$(docker exec "$c" sh -c "test -f /var/cache/bunkerweb/crowdsec/$1/crowdsec.conf && echo present || echo absent" 2>/dev/null | tr -d '\n') "
	done
	echo "$out"
}

wait_slow_start() { # n
	local deadline=$((SECONDS + 120))
	while [ "$(slow_starts)" -lt "$1" ]; do
		[ "$SECONDS" -lt "$deadline" ] || fail "the slow job never started (run $1)"
		sleep 1
	done
}

wait_conf_state() { # service want [scheduler]: with a third argument only the scheduler cache is judged
	local deadline=$((SECONDS + converge_timeout)) state=""
	while [ "$SECONDS" -lt "$deadline" ]; do
		state="$(conf_state "$1")"
		if [ -n "${3:-}" ]; then
			[ "${state%% *}" = "$2" ] && return 0
		else
			[ "$state" = "$2 $2 " ] && return 0
		fi
		sleep 3
	done
	return 1
}

base="$(slow_starts)"

echo "scheduler_change_claim: phase 1, create s1 (the slow job runs), then create s2 while it runs"
[ "$(api POST /services '{"server_name":"s1.test","variables":{"USE_CROWDSEC":"yes","SLOWJOB_TAG":"a"}}')" = "200" ] || fail "POST s1 failed"
wait_slow_start $((base + 1))
sleep 3
[ "$(api POST /services '{"server_name":"s2.test","variables":{"USE_CROWDSEC":"yes","SLOWJOB_TAG":"b"}}')" = "200" ] || fail "POST s2 failed"
wait_conf_state s2.test present || fail "s2 crowdsec.conf missing after a mid-cycle create [scheduler instance]: $(conf_state s2.test)"
echo "scheduler_change_claim: s2 crowdsec.conf generated and shipped to the instance"
# Captured first: `grep -q` closing the pipe would hand docker logs a SIGPIPE, which pipefail reports as a failure.
scheduler_logs="$(docker logs "$scheduler" 2>&1)"
grep -q 'CrowdSec configuration successfully generated for 2 service(s)' <<<"$scheduler_logs" || fail "no crowdsec-conf run saw both services"

echo "scheduler_change_claim: phase 2, touch s1 (the slow job runs), then disable CrowdSec on s2 while it runs"
# Let the cycle the s2 write started finish, so the next slow job is the one s1 starts.
deadline=$((SECONDS + converge_timeout))
until [ "$(slow_starts)" -eq "$(slow_ends)" ]; do
	[ "$SECONDS" -lt "$deadline" ] || fail "the slow job of phase 1 never ended"
	sleep 2
done
sleep 10
base="$(slow_starts)"
[ "$(api PATCH /services/s1.test '{"variables":{"SLOWJOB_TAG":"c"}}')" = "200" ] || fail "PATCH s1 failed"
wait_slow_start $((base + 1))
sleep 3
[ "$(api PATCH /services/s2.test '{"variables":{"USE_CROWDSEC":"no"}}')" = "200" ] || fail "PATCH s2 failed"
wait_conf_state s2.test absent || fail "s2 crowdsec.conf still present after a mid-cycle removal [scheduler instance]: $(conf_state s2.test)"
echo "scheduler_change_claim: s2 crowdsec.conf removed from the scheduler cache [scheduler instance]: $(conf_state s2.test)"

echo "scheduler_change_claim: all checks passed"
