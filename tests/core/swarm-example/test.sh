#!/bin/bash
# The scenario `examples/swarm-configs/` never had: it is one of the six example directories with
# no manifest in `examples/` and none in `tests/examples/` either, so nothing has ever exercised it.
#
# It is the only shipped example that demonstrates Swarm *configs* -- one global and three scoped
# with CONFIG_SITE -- through `docker config create`, which is the only route Swarm has for custom
# NGINX snippets (`bunkerweb.CUSTOM_CONF_*` labels are a Docker-autoconf feature and are inert
# under Swarm; the controller now says so rather than ignoring them silently).
#
# It runs against the same stack tests/core/swarm/test.sh uses, deployed here under its own name.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "swarm-example: only the docker integration drives this" >&2
	exit 1
fi

STACK="${BW_SWARM_EXAMPLE_STACK:-bw-swarm-example}"
API="http://127.0.0.1:${BW_SWARM_EXAMPLE_API_PORT:-8892}"
HTTP="http://127.0.0.1:${BW_SWARM_EXAMPLE_HTTP_PORT:-8082}"
TOKEN="secret"
EXAMPLE="examples/swarm-configs"

we_initialised_swarm=0
we_labelled_node=0
failures=0
workdir="$(mktemp -d)"

log() { echo "swarm-example: $*"; }
fail() {
	echo "swarm-example: FAIL: $*" >&2
	failures=$((failures + 1))
}
ok() { echo "swarm-example: ok: $*"; }

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

example_configs() { echo "cfg_all_server_http cfg_app1_server_http cfg_app2_server_http cfg_app3_server_http"; }

cleanup() {
	log "tearing down ..."
	docker stack rm "${STACK}-apps" >/dev/null 2>&1 || true
	docker stack rm "$STACK" >/dev/null 2>&1 || true
	for _ in {1..30}; do
		docker network ls --format '{{.Name}}' | grep -qE "^${STACK}(-apps)?_" || break
		sleep 1
	done
	for _ in {1..30}; do
		docker volume ls --format '{{.Name}}' | grep -q "^${STACK}_" || break
		docker volume ls --format '{{.Name}}' | grep "^${STACK}_" |
			while read -r volume; do docker volume rm -f "$volume" >/dev/null 2>&1 || true; done
		sleep 1
	done
	for config in $(example_configs); do docker config rm "$config" >/dev/null 2>&1 || true; done
	rm -rf "$workdir"
	if [ "$we_labelled_node" = "1" ]; then
		docker node update --label-rm bw-state "$(docker node ls --format '{{.ID}}' | head -1)" >/dev/null 2>&1 || true
	fi
	if [ "$we_initialised_swarm" = "1" ]; then
		docker swarm leave --force >/dev/null 2>&1 || true
	fi
}
trap cleanup EXIT

api() { curl -fsS -H "Authorization: Bearer ${TOKEN}" --max-time 15 "${API}$1"; }

# ---------------------------------------------------------------------------- host state

if [ "$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null)" != "active" ]; then
	docker swarm init --advertise-addr 127.0.0.1 >/dev/null
	we_initialised_swarm=1
fi
NODE="$(docker node ls --format '{{.ID}}' | head -1)"
if [ "$(docker node inspect "$NODE" --format '{{index .Spec.Labels "bw-state"}}' 2>/dev/null)" != "true" ]; then
	docker node update --label-add bw-state=true "$NODE" >/dev/null
	we_labelled_node=1
fi
docker stack rm "${STACK}-apps" "$STACK" >/dev/null 2>&1 || true
for config in $(example_configs); do docker config rm "$config" >/dev/null 2>&1 || true; done
for _ in {1..30}; do
	docker network ls --format '{{.Name}}' | grep -qE "^${STACK}(-apps)?_" || break
	sleep 1
done

# ------------------------------------------------------- the example's own placement constraint

# The example used to pin every application service to `node.role==worker`. On a single-node swarm
# the only node is a manager, so every task stayed Pending forever and the only shipped
# demonstration of Swarm configs was undeployable as written -- the exact trap the conception names
# ("no node.role constraints in test stacks"). The constraint is gone and this script now deploys
# the example AS SHIPPED; this is the regression guard that keeps it that way. A commented-out
# `placement:` block showing operators where to pin on a real cluster is fine and expected -- only
# an ACTIVE constraint breaks the example, so match one that is not commented out.
#
# The quote class covers all three block-sequence spellings YAML allows here: bare
# `- node.role==worker`, double-quoted and single-quoted. It does NOT match the flow form
# `constraints: ["node.role==worker"]`, which would slip past this guard -- accepted, because the
# example is block style throughout and a rewrite to flow style would be a visible, deliberate edit
# rather than the accidental re-add this guard exists to catch.
log "the shipped example must carry no active placement constraint"
if matches '^[[:space:]]*-[[:space:]]*['"'"'"]?node\.role' "$(cat "$EXAMPLE/swarm.yml")"; then
	fail "the example carries an active node.role constraint again; it cannot deploy on a single node"
else
	ok "the example carries no active placement constraint and deploys as shipped"
fi

# ----------------------------------------------------------------------------------- stack

log "deploying the BunkerWeb stack ..."
# NAMESPACES is dropped for this stack, deliberately. The example ships four configs created by
# its own setup-swarm.sh with no `bunkerweb.NAMESPACE` label -- as a reader following the example
# would have -- and the namespace filter correctly refuses them. Config labels cannot be added
# afterwards either: `docker config update --label-add` is not supported, which is the immutability
# this suite asserts elsewhere. Running the example the way its reader does is the point, so the
# filter is switched off here and the instance count is asserted below instead.
#
# Safe on a shared daemon: SwarmController discovers SERVICES, not containers, so a compose stack
# belonging to another lane is invisible to it. The instance-count assertion is what catches it if
# that ever stops being true.
sed -e "s/bw-swarm-test/${STACK}/g" \
	-e "s/published: 8080/published: ${HTTP##*:}/" \
	-e "s/published: 8443/published: 8445/" \
	-e "s/published: 8890/published: ${API##*:}/" \
	-e "s|10.55.60.0/24|10.55.62.0/24|g" \
	-e "/NAMESPACES:/d" \
	tests/swarm/stack.yml >"$workdir/stack.yml"
docker stack deploy -c "$workdir/stack.yml" --resolve-image never "$STACK" >/dev/null

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
	docker stack ps "$STACK" --no-trunc | head -20 || true
	echo "swarm-example: the stack never converged" >&2
	exit 1
fi

for _ in {1..60}; do
	matches "Listening for Swarm events" "$(docker service logs "${STACK}_bw-autoconf" --no-task-ids 2>&1)" && break
	sleep 2
done

# ------------------------------------------------------- the example's own setup script

log "running the example's setup-swarm.sh, unmodified, from the example directory"
(cd "$EXAMPLE" && ./setup-swarm.sh) >/dev/null 2>&1 || true
created="$(docker config ls --format '{{.Name}}' | grep -c '^cfg_.*_server_http$' || true)"
if [ "$created" -eq 4 ]; then
	ok "setup-swarm.sh created its 4 Swarm configs (1 global + 3 CONFIG_SITE)"
else
	fail "setup-swarm.sh created $created of 4 configs"
fi

# ------------------------------------------------------- the example's services

# Deployed AS SHIPPED. The one edit is the network name: the example's `bw-services` is created by
# the test stack under its own project prefix, so the reference has to be scoped. That is stack
# scoping, not a workaround for a defect in the example.
log "deploying the example's application services, as shipped"
sed -e "s/name: bw-services/name: ${STACK}_bw-services/" \
	"$EXAMPLE/swarm.yml" >"$workdir/apps.yml"
docker stack deploy -c "$workdir/apps.yml" --resolve-image never "${STACK}-apps" >/dev/null 2>&1 ||
	docker stack deploy -c "$workdir/apps.yml" "${STACK}-apps" >/dev/null

for _ in {1..60}; do
	if matches "app1.example.com" "$(api /services 2>/dev/null)"; then break; fi
	sleep 2
done

# With NAMESPACES off, the controller manages every BunkerWeb instance SERVICE on the daemon.
# Exactly one must be registered: more means another Swarm stack leaked into this one and every
# assertion below is measuring the wrong cluster.
instances="$(api /instances 2>/dev/null | python3 -c "
import json,sys
print(len(json.load(sys.stdin)['instances']))" 2>/dev/null || echo -1)"
if [ "$instances" = "1" ]; then
	ok "exactly one instance is registered, so nothing foreign leaked into this stack"
else
	fail "expected 1 registered instance, found $instances -- another Swarm stack is on this daemon"
fi

services="$(api /services 2>/dev/null || echo '{}')"
missing=""
for host in app1.example.com app2.example.com app3.example.com; do
	matches "$host" "$services" || missing="$missing $host"
done
if [ -z "$missing" ]; then
	ok "all three of the example's services were discovered from their deploy.labels"
else
	fail "the example's services never reached the control plane:$missing"
fi

# ------------------------------------------------------- the configs the example exists to show

log "checking the example's configs landed with the right scope"
configs="$(api /configs 2>/dev/null || echo '{}')"
scope_of() {
	echo "$configs" | python3 -c "
import json,sys
name = sys.argv[1]
match = [c for c in json.load(sys.stdin).get('configs', []) if c['name'] == name]
print(match[0]['service'] if match else 'MISSING')" "$1" 2>/dev/null || echo MISSING
}

if [ "$(scope_of cfg_all_server_http)" = "global" ]; then
	ok "the example's unscoped config is global"
else
	fail "cfg_all_server_http is scoped '$(scope_of cfg_all_server_http)', expected global"
fi
for n in 1 2 3; do
	actual="$(scope_of "cfg_app${n}_server_http")"
	if [ "$actual" = "app${n}.example.com" ]; then
		ok "the example's CONFIG_SITE config for app${n} is scoped to app${n}.example.com"
	else
		fail "cfg_app${n}_server_http is scoped '$actual', expected app${n}.example.com"
	fi
done

# Served, not merely recorded. The example's per-site configs each add a /hello location.
if [ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: app1.example.com' "$HTTP/" --max-time 10)" = "200" ]; then
	ok "BunkerWeb serves the example's app1 through the reverse proxy labels"
else
	fail "app1.example.com is configured but not served"
fi

if [ "$failures" -ne 0 ]; then
	echo "swarm-example: $failures check(s) failed" >&2
	exit 1
fi
echo "swarm-example: all checks passed"
