#!/bin/bash
# Swarm integration gate.
#
# Why this is a `script` action and not a set of assertion types: none of what has to hold here is
# expressible as "one configured stack, some HTTP assertions". It is `docker swarm init`, a
# `docker stack deploy`, Swarm `config` objects, service labels and `docker service update` --
# a lifecycle, not a request. `tests/core/internalcert/test.sh` set the precedent.
#
# It brings up its OWN stack (tests/swarm/stack.yml) on its own ports and networks and removes it
# again, so the framework's stack is untouched and `restart_stack: false` in the spec is honest.
#
# Host state: this initialises Swarm if the daemon is not already in it, and LEAVES IT AS FOUND.
# Same for the `bw-state` node label the stack's placement constraints target.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "swarm: only the docker integration drives this" >&2
	exit 1
fi

STACK="${BW_SWARM_STACK:-bw-swarm-test}"
API="http://127.0.0.1:${BW_SWARM_API_PORT:-8890}"
HTTP="http://127.0.0.1:${BW_SWARM_HTTP_PORT:-8083}"
TOKEN="secret"
STACK_FILE="tests/swarm/stack.yml"

we_initialised_swarm=0
we_labelled_node=0
failures=0

log() { echo "swarm: $*"; }
fail() {
	echo "swarm: FAIL: $*" >&2
	failures=$((failures + 1))
}
ok() { echo "swarm: ok: $*"; }

# `PRODUCER | grep -q PATTERN` is a trap under `set -o pipefail`, and it cost a full run to find:
# `grep -q` exits at the FIRST match, which SIGPIPEs the producer, whose non-zero status then fails
# the whole pipeline -- so a SUCCESSFUL match is reported as no match. It only bites while the
# producer is still writing, i.e. when the output is large, so the same assertion passes on a short
# log and fails on a long one. That is an intermittent INVERSION of a test result, which is worse
# than an outright failure. `$(...)` runs the producer to completion first, so there is no pipe to
# break. Every log/inspect/API assertion below goes through this.
matches() {
	local pattern="$1" haystack="$2"
	grep -qE -- "$pattern" <<<"$haystack"
}

cleanup() {
	log "tearing down ..."
	for service in app badinstance ign1 ign2; do
		docker service rm "${STACK}-${service}" >/dev/null 2>&1 || true
	done
	for config in ok.conf ok.conf.v2 foreign.conf site.conf; do
		docker config rm "${STACK}-${config}" >/dev/null 2>&1 || true
	done
	docker stack rm "$STACK" >/dev/null 2>&1 || true
	# `docker stack rm` returns before the networks are gone; a follow-up run that recreates them
	# too early fails with "network is in use by task".
	for _ in {1..30}; do
		docker network ls --format '{{.Name}}' | grep -q "^${STACK}_" || break
		sleep 1
	done
	# `docker stack rm` does NOT remove named volumes, and this stack keeps its whole database in
	# one. Leaving them behind means the next run boots on the previous run's configuration and
	# asserts against rows it never created -- the same trap tests/README.md documents for
	# bw-storage under the compose harness. Found the hard way: a rotation check compared a
	# checksum against a config row a PREVIOUS run had left in the database.
	for _ in {1..30}; do
		docker volume ls --format '{{.Name}}' | grep -q "^${STACK}_" || break
		docker volume ls --format '{{.Name}}' | grep "^${STACK}_" |
			while read -r volume; do docker volume rm -f "$volume" >/dev/null 2>&1 || true; done
		sleep 1
	done
	if [ "$we_labelled_node" = "1" ]; then
		docker node update --label-rm bw-state "$(docker node ls --format '{{.ID}}' | head -1)" >/dev/null 2>&1 || true
	fi
	if [ "$we_initialised_swarm" = "1" ]; then
		docker swarm leave --force >/dev/null 2>&1 || true
	fi
}
trap cleanup EXIT

api() { curl -fsS -H "Authorization: Bearer ${TOKEN}" --max-time 15 "${API}$1"; }

# jq is not a dependency of this suite; python3 is (the runner is python).
pyjson() { python3 -c "$1"; }

autoconf_log() { docker service logs "${STACK}_bw-autoconf" --no-task-ids 2>&1; }

# --------------------------------------------------------------------------------- host state

if [ "$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null)" != "active" ]; then
	log "daemon is not in a swarm, initialising (and will leave again at the end)"
	docker swarm init --advertise-addr 127.0.0.1 >/dev/null
	we_initialised_swarm=1
else
	log "daemon is already a swarm node, leaving that as it is"
fi

NODE="$(docker node ls --format '{{.ID}}' | head -1)"
if [ "$(docker node inspect "$NODE" --format '{{index .Spec.Labels "bw-state"}}' 2>/dev/null)" != "true" ]; then
	docker node update --label-add bw-state=true "$NODE" >/dev/null
	we_labelled_node=1
fi

# A previous aborted run leaves the stack behind; deploying over it is not the same as deploying it.
docker stack rm "$STACK" >/dev/null 2>&1 || true
for _ in {1..30}; do
	docker network ls --format '{{.Name}}' | grep -q "^${STACK}_" || break
	sleep 1
done

# --------------------------------------------------------------------------------- deploy

log "deploying $STACK_FILE ..."
# --resolve-image never: the images are local `:tests` builds with no registry behind them, and
# the default (`always`) makes stack deploy try to resolve a digest and fail.
docker stack deploy -c "$STACK_FILE" --resolve-image never "$STACK" >/dev/null

log "waiting for every service to converge ..."
converged=0
for _ in {1..90}; do
	pending="$(docker service ls --filter "label=com.docker.stack.namespace=$STACK" --format '{{.Replicas}}' |
		awk -F/ '$1 != $2' | grep -c . || true)"
	if [ "$pending" = "0" ]; then
		converged=1
		break
	fi
	sleep 2
done
if [ "$converged" != "1" ]; then
	docker service ls --filter "label=com.docker.stack.namespace=$STACK"
	docker stack ps "$STACK" --no-trunc | head -20 || true
	echo "swarm: the stack never converged" >&2
	exit 1
fi
ok "the whole stack converged with no depends_on: docker stack deploy ignores that key"

# ------------------------------------------- criterion 2: autoconf leaves its ping loop

log "criterion 2: bw-autoconf must leave the API ping loop and listen for Swarm events"
listening=0
for _ in {1..60}; do
	if matches "Listening for Swarm events" "$(autoconf_log)"; then
		listening=1
		break
	fi
	sleep 2
done
if [ "$listening" = "1" ]; then
	ok "criterion 2: bw-autoconf is listening for Swarm events"
else
	autoconf_log | tail -30
	fail "criterion 2: bw-autoconf never reached 'Listening for Swarm events'"
fi
# The published 1.7 stack loops forever on this line because it carries no bw-api and no API_URL.
# Reaching 'API is available' is the specific regression this whole chantier exists to close.
if matches "API is available" "$(autoconf_log)"; then
	ok "criterion 2: the API ping loop terminated ('API is available')"
else
	fail "criterion 2: bw-autoconf never saw the API come up"
fi

wait_for_deploy() {
	for _ in {1..40}; do
		sleep 1
		if matches "Successfully deployed new configuration" "$(autoconf_log)"; then return 0; fi
	done
	return 1
}

# ------------------------------------------------------------------- discovery: create

log "discovery: creating a service labelled bunkerweb.SERVER_NAME"
docker service create --name "${STACK}-app" --detach \
	--network "${STACK}_bw-services" \
	--label "com.docker.stack.namespace=$STACK" \
	--label "bunkerweb.NAMESPACE=$STACK" \
	--label "bunkerweb.SERVER_NAME=app.example.com" \
	--label "bunkerweb.USE_REVERSE_PROXY=yes" \
	--label "bunkerweb.REVERSE_PROXY_URL=/" \
	--label "bunkerweb.REVERSE_PROXY_HOST=http://${STACK}-app:8080" \
	bunkerity/bunkerweb-hello:v1.0 >/dev/null

found=0
for _ in {1..40}; do
	if matches "app.example.com" "$(api /services 2>/dev/null)"; then
		found=1
		break
	fi
	sleep 2
done
if [ "$found" = "1" ]; then
	ok "discovery: the labelled service reached the control plane"
else
	fail "discovery: app.example.com never appeared in /services"
fi

# Served end to end, not merely recorded: the label has to become nginx configuration on the
# instance. Host-mode publishing means this is the real client IP path, not the routing mesh.
served=0
for _ in {1..30}; do
	if [ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: app.example.com' "$HTTP/" --max-time 10)" = "200" ]; then
		served=1
		break
	fi
	sleep 2
done
if [ "$served" = "1" ]; then
	ok "discovery: BunkerWeb serves the discovered service"
else
	fail "discovery: app.example.com is configured but not served"
fi

# ------------------------------------------------------------------- R6: mode:global guard

log "R6: a replicated service labelled bunkerweb.INSTANCE must be refused"
docker service create --name "${STACK}-badinstance" --detach --replicas 2 \
	--network "${STACK}_bw-universe" \
	--label "com.docker.stack.namespace=$STACK" \
	--label "bunkerweb.NAMESPACE=$STACK" \
	--label "bunkerweb.INSTANCE=yes" \
	nginx:alpine >/dev/null

refused=0
for _ in {1..30}; do
	if matches "labelled bunkerweb.INSTANCE: it is not a global service" "$(autoconf_log)"; then
		refused=1
		break
	fi
	sleep 2
done
if [ "$refused" = "1" ]; then
	ok "R6: the replicated INSTANCE service was refused, with a reason"
else
	fail "R6: the controller accepted a replicated bunkerweb.INSTANCE service"
fi

# Refusing in the log is not refusing in the database. The tasks of a replicated service resolve
# as <service>.<slot>.<TaskID> and can never be reached, so registering one is the actual defect.
instances="$(api /instances | pyjson 'import json,sys; print(json.load(sys.stdin)["instances"].__len__())' 2>/dev/null || echo -1)"
if [ "$instances" = "1" ]; then
	ok "R6: exactly one instance is registered, so the refusal was real"
else
	fail "R6: expected 1 registered instance, found $instances"
fi

hostname="$(api /instances | pyjson 'import json,sys; print(json.load(sys.stdin)["instances"][0]["hostname"])' 2>/dev/null || echo "")"
case "$hostname" in
# R6 settled that task identity is KEPT: <service>.<NodeID>.<TaskID>, no model change.
*.*.*) ok "R6: the instance keeps task identity ($hostname)" ;;
*) fail "R6: instance hostname is not <service>.<NodeID>.<TaskID>: '$hostname'" ;;
esac

# ------------------------------------------------------- Swarm configs, global and CONFIG_SITE

log "configs: a global one, one for another namespace, one scoped with CONFIG_SITE"
printf 'location /swarm-config-probe { return 200 "swarm-config-applied"; }\n' |
	docker config create --label bunkerweb.CONFIG_TYPE=server-http --label "bunkerweb.NAMESPACE=$STACK" "${STACK}-ok.conf" - >/dev/null
printf 'location /swarm-foreign-probe { return 200 "leaked"; }\n' |
	docker config create --label bunkerweb.CONFIG_TYPE=server-http --label "bunkerweb.NAMESPACE=someone-else" "${STACK}-foreign.conf" - >/dev/null
printf 'location /swarm-site-probe { return 200 "site-scoped"; }\n' |
	docker config create --label bunkerweb.CONFIG_TYPE=server-http --label "bunkerweb.NAMESPACE=$STACK" --label bunkerweb.CONFIG_SITE=app.example.com "${STACK}-site.conf" - >/dev/null

for _ in {1..40}; do
	matches "${STACK}-ok" "$(api /configs 2>/dev/null)" && break
	sleep 2
done

configs="$(api /configs)"
if matches "${STACK}-ok" "$configs"; then
	ok "configs: the global config was collected"
else
	fail "configs: the in-namespace global config never arrived"
fi

# NAMESPACES used to filter the event path and service discovery but NOT get_configs, so a global
# config labelled for another namespace was collected by every autoconf partition on the daemon.
if matches "${STACK}-foreign" "$configs"; then
	fail "namespaces: a config labelled for another namespace leaked into this partition"
else
	ok "namespaces: the foreign-namespace config was ignored"
fi

site_scope="$(echo "$configs" | pyjson "
import json,sys
configs = json.load(sys.stdin)['configs']
match = [c for c in configs if c['name'].endswith('-site')]
print(match[0]['service'] if match else 'MISSING')
" 2>/dev/null || echo MISSING)"
if [ "$site_scope" = "app.example.com" ]; then
	ok "configs: CONFIG_SITE scoped the config to app.example.com"
else
	fail "configs: CONFIG_SITE config is scoped to '$site_scope', expected app.example.com"
fi

# ------------------------------------------------------------------- config rotation

log "immutability: rotation is a NEW named object plus a remove, never an in-place update"
# Swarm refuses to change anything but Labels on a config or a secret. Assert that rather than
# assuming it: the whole rotation design rests on it.
if docker config create --label bunkerweb.CONFIG_TYPE=server-http "${STACK}-ok.conf" - </dev/null >/dev/null 2>&1; then
	fail "immutability: the daemon accepted a second config under an existing name"
else
	ok "immutability: a config name cannot be reused, so versioning by name is mandatory"
fi

before="$(echo "$configs" | pyjson "
import json,sys
match = [c for c in json.load(sys.stdin)['configs'] if c['service'] == 'global']
print(match[0]['checksum'] if match else '')" 2>/dev/null || echo "")"
printf 'location /swarm-config-probe { return 200 "swarm-config-rotated"; }\n' |
	docker config create --label bunkerweb.CONFIG_TYPE=server-http --label "bunkerweb.NAMESPACE=$STACK" "${STACK}-ok.conf.v2" - >/dev/null
docker config rm "${STACK}-ok.conf" >/dev/null

rotated=0
for _ in {1..40}; do
	after="$(api /configs 2>/dev/null | pyjson "
import json,sys
match = [c for c in json.load(sys.stdin)['configs'] if c['service'] == 'global']
print(match[0]['checksum'] if match else '')" 2>/dev/null || echo "")"
	if [ -n "$after" ] && [ "$after" != "$before" ]; then
		rotated=1
		break
	fi
	sleep 2
done
if [ "$rotated" = "1" ]; then
	ok "immutability: the rotated config replaced the old content"
else
	fail "immutability: the global config content did not change after rotation"
fi

# ------------------------------------------------------------------- SWARM_IGNORE_LABELS

log "SWARM_IGNORE_LABELS: one full key, one bare suffix"
docker service create --name "${STACK}-ign1" --detach --network "${STACK}_bw-services" \
	--label "com.docker.stack.namespace=$STACK" --label "bunkerweb.NAMESPACE=$STACK" \
	--label "bunkerweb.SERVER_NAME=ign1.example.com" --label "bunkerweb.IGNORED_FULL_KEY=1" \
	bunkerity/bunkerweb-hello:v1.0 >/dev/null
docker service create --name "${STACK}-ign2" --detach --network "${STACK}_bw-services" \
	--label "com.docker.stack.namespace=$STACK" --label "bunkerweb.NAMESPACE=$STACK" \
	--label "bunkerweb.SERVER_NAME=ign2.example.com" --label "bunkerweb.IGNORED_SUFFIX=1" \
	bunkerity/bunkerweb-hello:v1.0 >/dev/null

# Wait for a reconcile that could have picked them up, so "absent" means filtered and not "early".
sleep 20
for _ in {1..20}; do
	matches "ign1[.]example[.]com|ign2[.]example[.]com" "$(api /services 2>/dev/null)" && break
	sleep 2
done
services="$(api /services)"
if matches "ign1.example.com" "$services"; then
	fail "SWARM_IGNORE_LABELS: the full-key ignore did not filter the service"
else
	ok "SWARM_IGNORE_LABELS: full key 'bunkerweb.IGNORED_FULL_KEY' filtered the service"
fi
if matches "ign2.example.com" "$services"; then
	fail "SWARM_IGNORE_LABELS: the bare-suffix ignore did not filter the service"
else
	ok "SWARM_IGNORE_LABELS: bare suffix 'IGNORED_SUFFIX' filtered the service"
fi
# RULE 13 floor: if discovery were broken outright, both checks above would pass for the wrong
# reason. The service that is NOT ignored has to still be there.
matches "app.example.com" "$services" ||
	fail "SWARM_IGNORE_LABELS: nothing at all is discovered, so the two checks above prove nothing"

# --------------------------------------------------- criterion 4: service update reconfigures

log "criterion 4: docker service update must reconfigure within 30 s"
started="$(date +%s)"
docker service update --detach --label-add bunkerweb.USE_GZIP=yes "${STACK}-app" >/dev/null
reconfigured=0
for _ in {1..30}; do
	if matches '"USE_GZIP"' "$(api /services/app.example.com 2>/dev/null || true)"; then
		reconfigured=1
		break
	fi
	sleep 1
done
elapsed=$(($(date +%s) - started))
if [ "$reconfigured" = "1" ] && [ "$elapsed" -lt 30 ]; then
	ok "criterion 4: reconfiguration observed ${elapsed}s after the service update"
else
	fail "criterion 4: no reconfiguration within 30 s (waited ${elapsed}s)"
fi

# ------------------------------------------------- criterion 3: a background job runs end to end

log "criterion 3: a background job must run through the worker and leave a job-cache entry"
cached=0
for _ in {1..60}; do
	if api /jobs 2>/dev/null | pyjson "
import json,sys
jobs = json.load(sys.stdin)['jobs']
sys.exit(0 if (jobs.get('geoip-country') or {}).get('cache') else 1)" 2>/dev/null; then
		cached=1
		break
	fi
	sleep 5
done
if [ "$cached" = "1" ]; then
	ok "criterion 3: geoip-country left a job-cache entry"
else
	# Name what did run rather than only reporting the miss: a worker that executed nothing at all
	# and a worker that executed everything except this job are different defects.
	api /jobs 2>/dev/null | pyjson "
import json,sys
jobs = json.load(sys.stdin)['jobs']
with_cache = sorted(name for name, job in jobs.items() if job.get('cache'))
print(f'swarm: jobs known: {len(jobs)}, jobs with a cache entry: {with_cache}', file=sys.stderr)" || true
	fail "criterion 3: geoip-country never left a job-cache entry"
fi

# ----------------------------------------------------------------------------------- verdict

if [ "$failures" -ne 0 ]; then
	echo "swarm: $failures check(s) failed" >&2
	exit 1
fi
echo "swarm: all checks passed"
