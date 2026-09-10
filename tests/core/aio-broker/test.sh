#!/bin/bash

set -Eeuo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
container="bunkerweb-all-in-one"

# run.sh sources utils.sh in its own shell and exports BW_VERSION there, but this probe runs as
# a `script` action (tests/core_handlers/script_handler.py's subprocess.run, no env= override) --
# on CI that export never reaches this process, so `docker compose up/down` recreates the
# container from an empty tag ("invalid reference format"). Resolve it ourselves.
if [ -z "${BW_VERSION:-}" ]; then
	if [ -r /tmp/bw_version.txt ]; then
		BW_VERSION="$(cat /tmp/bw_version.txt)"
	else
		image="$(docker inspect --format '{{.Config.Image}}' "$container" 2>/dev/null || true)"
		BW_VERSION="${image##*:}"
	fi
fi
[ -n "${BW_VERSION:-}" ] || { echo "aio-broker: unable to resolve BW_VERSION (not set, /tmp/bw_version.txt unreadable, and no running '$container' container to read the image tag from)" >&2; exit 1; }
export BW_VERSION

compose_file="${AIO_BROKER_COMPOSE_FILE:-${root}/tests/docker/docker-compose.all-in-one.yml}"
compose=(docker compose -p docker -f "$compose_file")

fail() {
	docker inspect --format 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || true
	echo "aio-broker: $*" >&2
	exit 1
}

health_status() {
	docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || true
}

wait_for_health() {
	local expected="$1"
	local timeout="$2"
	local started=$SECONDS
	local state

	for ((attempt = 0; attempt < timeout; attempt++)); do
		state="$(health_status)"
		if [ "$state" = "$expected" ]; then
			echo "$((SECONDS - started))"
			return 0
		fi
		sleep 1
	done
	return 1
}

run_healthcheck_test() {
	local down_seconds health_log up_seconds

	[ "$(health_status)" = "healthy" ] || fail "container was not healthy before stopping the broker"
	trap 'docker exec "$container" supervisorctl start broker >/dev/null 2>&1 || true' EXIT
	docker exec "$container" supervisorctl stop broker >/dev/null

	if ! down_seconds="$(wait_for_health unhealthy 100)"; then
		fail "container did not become unhealthy after the broker stopped"
	fi
	health_log="$(docker inspect --format '{{range .State.Health.Log}}{{.Output}}{{"\n"}}{{end}}' "$container")"
	grep -Fq "Dedicated job broker is not running: broker" <<<"$health_log" || fail "health log did not identify the dedicated broker"
	grep -Fq "STOPPED" <<<"$health_log" || fail "health log did not report the stopped supervisor program"

	docker exec "$container" supervisorctl start broker >/dev/null
	if ! up_seconds="$(wait_for_health healthy 30)"; then
		fail "container did not recover after the broker restarted"
	fi
	trap - EXIT

	echo "healthcheck: unhealthy=${down_seconds}s healthy=${up_seconds}s"
}

queue_length() {
	docker exec "$container" redis-cli -p 6380 LLEN "$1"
}

capture_task_ids() {
	docker exec "$container" python3 -c '
import json
import subprocess

for queue in ("default", "heavy"):
    output = subprocess.check_output(["redis-cli", "-p", "6380", "--raw", "LRANGE", queue, "0", "-1"], text=True)
    for message in output.splitlines():
        print(json.loads(message)["headers"]["id"])
'
}

attempt_count() {
	local keys=()
	local task_id

	for task_id in "$@"; do
		keys+=("bw:job_attempt:${task_id}")
	done
	docker exec "$container" redis-cli -p 6380 EXISTS "${keys[@]}"
}

recover_persistence_test() {
	"${compose[@]}" up -d >/dev/null 2>&1 || true
	docker exec "$container" supervisorctl start broker worker scheduler >/dev/null 2>&1 || true
}

run_persistence_test() {
	local before_id after_id volume_before volume_after
	local runs_before runs_after default_count heavy_count total queued_stable=0 previous_total=-1
	local healthy_seconds executed=0 ids_file
	local -a task_ids

	[ "$(health_status)" = "healthy" ] || fail "container was not healthy before queueing jobs"
	ids_file="$(mktemp)"
	trap 'rm -f "$ids_file"; recover_persistence_test' EXIT

	before_id="$(docker inspect --format '{{.Id}}' "$container")"
	volume_before="$(docker volume inspect --format '{{.CreatedAt}}' bw-storage)"
	runs_before="$(docker exec "$container" sqlite3 /var/lib/bunkerweb/db.sqlite3 'SELECT COUNT(*) FROM bw_jobs_runs;')"
	docker exec "$container" supervisorctl stop worker >/dev/null
	docker exec "$container" supervisorctl restart scheduler >/dev/null

	for _ in {1..60}; do
		default_count="$(queue_length default)"
		heavy_count="$(queue_length heavy)"
		total=$((default_count + heavy_count))
		if [ "$total" -gt 0 ] && [ "$total" -eq "$previous_total" ]; then
			queued_stable=$((queued_stable + 1))
		else
			queued_stable=0
		fi
		[ "$queued_stable" -ge 2 ] && break
		previous_total="$total"
		sleep 1
	done
	[ "${total:-0}" -gt 0 ] || fail "scheduler queued no jobs while the worker was stopped"

	capture_task_ids >"$ids_file"
	mapfile -t task_ids <"$ids_file"
	[ "${#task_ids[@]}" -eq "$total" ] || fail "captured ${#task_ids[@]} task ids from ${total} queued messages"
	[ "$(attempt_count "${task_ids[@]}")" -eq 0 ] || fail "a queued task was already attempted before recreation"

	"${compose[@]}" down >/dev/null
	volume_after="$(docker volume inspect --format '{{.CreatedAt}}' bw-storage)"
	[ "$volume_after" = "$volume_before" ] || fail "bw-storage did not survive docker compose down"
	"${compose[@]}" up -d >/dev/null

	if ! healthy_seconds="$(wait_for_health healthy 180)"; then
		fail "recreated container did not become healthy"
	fi
	after_id="$(docker inspect --format '{{.Id}}' "$container")"
	[ "$after_id" != "$before_id" ] || fail "docker compose did not recreate the container"

	for _ in {1..180}; do
		executed="$(attempt_count "${task_ids[@]}")"
		[ "$executed" -eq "${#task_ids[@]}" ] && break
		sleep 1
	done
	[ "$executed" -eq "${#task_ids[@]}" ] || fail "$(( ${#task_ids[@]} - executed )) queued task(s) were missing after recreation"

	runs_after="$(docker exec "$container" sqlite3 /var/lib/bunkerweb/db.sqlite3 'SELECT COUNT(*) FROM bw_jobs_runs;')"
	rm -f "$ids_file"
	trap - EXIT

	echo "persistence: queued=${#task_ids[@]} default=${default_count} heavy=${heavy_count} executed=${executed} missing=0 runs=${runs_before}->${runs_after} healthy=${healthy_seconds}s"
}

case "${1:-}" in
	healthcheck)
		run_healthcheck_test
		;;
	persistence)
		run_persistence_test
		;;
	*)
		echo "usage: $0 healthcheck|persistence" >&2
		exit 2
		;;
esac
