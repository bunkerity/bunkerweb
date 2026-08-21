#!/bin/bash
# Criterion 5: a custom certificate whose PRIVATE KEY is a Swarm secret mounted on bw-worker is
# served by the instance.
#
# The design this proves, and why it is the only one available:
#
#   * A Swarm SECRET's payload is never returned by the Engine API. swarmkit sets Spec.Data to nil
#     on every read path (GetSecret, ListSecrets, UpdateSecret, CreateSecret), by design and with
#     no flag to turn it off. So the controller CANNOT read a secret and pass it along the way the
#     Kubernetes controller reads secret.data. The earlier "controller reads Swarm secrets" design
#     is impossible, not merely awkward.
#   * A Swarm CONFIG is readable -- which is exactly why SwarmController collects configs -- and
#     is therefore fine for the CERTIFICATE. It is NOT fine for the key: configs are unencrypted
#     in the raft store on every manager node.
#   * So the key is mounted as a secret on the service that actually needs it, and the label
#     carries only a PATH. The key never passes through the controller or the API.
#
# The one component that needs it is the WORKER: since 1.7 the scheduler dispatches and the
# `custom-cert` job runs in bw-worker. Mounting the key on the scheduler -- which is what the
# customcert help strings said until this chantier -- puts it on a container that never opens it.
#
# Accepted limitation this test also demonstrates: `docker service update --secret-add` RESTARTS
# the worker task. Adding or rotating a certificate therefore puts a control-plane restart on the
# "I add a site" path.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "swarm-secrets: only the docker integration drives this" >&2
	exit 1
fi

STACK="${BW_SWARM_SECRETS_STACK:-bw-swarm-secrets}"
API="http://127.0.0.1:${BW_SWARM_SECRETS_API_PORT:-8891}"
HTTPS="https://127.0.0.1:${BW_SWARM_SECRETS_HTTPS_PORT:-8444}"
TOKEN="secret"
DOMAIN="secret.example.com"

we_initialised_swarm=0
we_labelled_node=0
failures=0
workdir="$(mktemp -d)"

log() { echo "swarm-secrets: $*"; }
fail() {
	echo "swarm-secrets: FAIL: $*" >&2
	failures=$((failures + 1))
}
ok() { echo "swarm-secrets: ok: $*"; }

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
	docker service rm "${STACK}-app" >/dev/null 2>&1 || true
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
	# Secrets and configs are refused while a service still references them, so these come last.
	# `.key.v2` included: the rotation check attaches it to bw-worker, so the inline `secret rm`
	# down there cannot succeed -- docker refuses to remove a secret still in use, and the `|| true`
	# hid it. It was found as one stray secret left on the daemon after an otherwise clean run.
	docker secret rm "${DOMAIN}.key.v1" "${DOMAIN}.key.v2" >/dev/null 2>&1 || true
	docker config rm "${DOMAIN}.pem.v1" >/dev/null 2>&1 || true
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
	log "daemon is not in a swarm, initialising (and will leave again at the end)"
	docker swarm init --advertise-addr 127.0.0.1 >/dev/null
	we_initialised_swarm=1
fi
NODE="$(docker node ls --format '{{.ID}}' | head -1)"
if [ "$(docker node inspect "$NODE" --format '{{index .Spec.Labels "bw-state"}}' 2>/dev/null)" != "true" ]; then
	docker node update --label-add bw-state=true "$NODE" >/dev/null
	we_labelled_node=1
fi

docker stack rm "$STACK" >/dev/null 2>&1 || true
docker secret rm "${DOMAIN}.key.v1" "${DOMAIN}.key.v2" >/dev/null 2>&1 || true
docker config rm "${DOMAIN}.pem.v1" >/dev/null 2>&1 || true
for _ in {1..30}; do
	docker network ls --format '{{.Name}}' | grep -q "^${STACK}_" || break
	sleep 1
done

# ------------------------------------------------------------------ certificate material

log "generating a self-signed certificate for ${DOMAIN}"
openssl req -x509 -newkey rsa:2048 -nodes -days 2 \
	-subj "/CN=${DOMAIN}" -addext "subjectAltName=DNS:${DOMAIN}" \
	-keyout "$workdir/key.pem" -out "$workdir/cert.pem" >/dev/null 2>&1
expected_fingerprint="$(openssl x509 -in "$workdir/cert.pem" -noout -fingerprint -sha256)"

# The KEY as a SECRET, the CERTIFICATE as a CONFIG. Names carry a version from the start: both
# object types are immutable, so rotation can only ever be "new name, then service update".
docker secret create "${DOMAIN}.key.v1" "$workdir/key.pem" >/dev/null
docker config create "${DOMAIN}.pem.v1" "$workdir/cert.pem" >/dev/null
ok "the private key is a Swarm secret and the certificate a Swarm config"

# The claim the whole design rests on, asserted rather than assumed. Read through JSON, NOT through
# `--format '{{.Spec.Data}}'`: a Go template renders a []byte as a decimal list, so a base64 test
# against that output fails for both object types and proves nothing about either.
payload_length() {
	docker "$1" inspect "$2" 2>/dev/null | python3 -c "
import json, sys
spec = json.load(sys.stdin)[0]['Spec']
print(len(spec.get('Data') or ''))" 2>/dev/null || echo 0
}

secret_payload="$(payload_length secret "${DOMAIN}.key.v1")"
if [ "$secret_payload" -gt 0 ]; then
	fail "the Engine returned ${secret_payload} bytes of secret payload -- the controller-reads-secrets design would be possible after all"
else
	ok "the Engine returns no secret payload at all, so the key can never reach the controller"
fi
# The contrast that justifies key-as-secret rather than key-as-config, and simultaneously the
# reason SwarmController CAN collect configs: their payload comes back and a secret's does not.
config_payload="$(payload_length config "${DOMAIN}.pem.v1")"
if [ "$config_payload" -gt 0 ]; then
	ok "a config's payload IS returned (${config_payload} bytes) -- which is why a private key must never be one"
else
	fail "a Swarm config payload was not returned, which contradicts how SwarmController collects configs"
fi

# ------------------------------------------------------------------------------- deploy

log "deploying the stack with the key mounted on bw-worker ..."
docker stack deploy -c tests/swarm/stack.secrets.yml --resolve-image never "$STACK" >/dev/null

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
	docker stack ps "$STACK" --no-trunc | head -20 || true
	echo "swarm-secrets: the stack never converged" >&2
	exit 1
fi

# The mount is what makes this design work at all: the job opens a path, not an API object.
if matches "${DOMAIN//./[.]}[.]key" "$(docker service inspect "${STACK}_bw-worker" \
	--format '{{range .Spec.TaskTemplate.ContainerSpec.Secrets}}{{.File.Name}} {{end}}' 2>/dev/null || true)"; then
	ok "the key is mounted on bw-worker, which is where the custom-cert job runs"
else
	fail "bw-worker has no secret mounted; the custom-cert job would never find the key"
fi

# Regression guard for the defect this test found the hard way, now asserted the right way round.
# `handle_docker_secrets` (src/common/helpers/utils.sh) exports every file in /run/secrets as
# `${NAME^^}`; `secret.example.com.key` uppercases to a name `export` refuses, and bw-worker -- the
# one entrypoint of seven with `set -e` -- died at boot, with the PEM written to the log on the way
# out by every entrypoint. The export is guarded now, so the DOTTED NAME AT THE DEFAULT LOCATION is
# exactly what has to keep working: that is the regression case, not something to route around.
if [ "$(docker service ls --filter "name=${STACK}_bw-worker" --format '{{.Replicas}}')" = "1/1" ]; then
	ok "bw-worker boots with a dot-named secret mounted at /run/secrets (the case that used to kill it)"
else
	docker service ps "${STACK}_bw-worker" --no-trunc | head -4 >&2 || true
	fail "bw-worker is not running with the material mounted -- the entrypoint secrets guard has regressed"
fi
# The silent half: the key's contents must not appear in any container log.
if matches "BEGIN PRIVATE KEY" "$(docker service logs "${STACK}_bw-worker" --no-task-ids 2>&1)"; then
	fail "the private key was written into the worker's log"
else
	ok "no key material in the worker's log"
fi
# And the skip has to be reported, not silent, so an operator can tell why it is not in the env.
if matches "Skipped Docker secret" "$(docker service logs "${STACK}_bw-worker" --no-task-ids 2>&1)"; then
	ok "the entrypoint reported the skipped secret by name"
else
	# Dump what the entrypoint actually said: a missing diagnostic and a secrets directory the
	# container could not read look identical from the outside, and they are different defects.
	docker service logs "${STACK}_bw-worker" --no-task-ids 2>&1 | grep -i "ENTRYPOINT" | head -8 >&2 || true
	fail "the entrypoint did not report skipping ${DOMAIN}.key; the operator gets no diagnostic"
fi
# Not on the scheduler: 1.7 moved job execution off it, and the customcert help strings said
# otherwise until this chantier.
#
# This assertion passes on an EMPTY producer, which makes it the one shape that can go false-GREEN:
# "no secret is mounted" and "inspect produced nothing at all" are the same empty string, and the
# `|| true` that stops a daemon error aborting the script also erases the difference. A renamed
# service, a stack that never converged or a docker failure would all read as "correctly not
# mounted". So the format emits `.Spec.Name` first and that name is required before the key pattern
# is evaluated at all: the floor proves the producer actually described the service we asked about.
# (The bw-worker check above needs no such floor -- there the match branch is the SUCCESS branch, so
# an empty producer fails loudly instead of passing quietly.)
scheduler_secrets="$(docker service inspect "${STACK}_bw-scheduler" \
	--format '{{.Spec.Name}} {{range .Spec.TaskTemplate.ContainerSpec.Secrets}}{{.File.Name}} {{end}}' 2>/dev/null || true)"
if ! matches "^${STACK//./[.]}_bw-scheduler([[:space:]]|$)" "$scheduler_secrets"; then
	fail "docker service inspect returned nothing usable for ${STACK}_bw-scheduler (got: ${scheduler_secrets:-<empty>}); cannot tell 'no key mounted' from 'inspect failed'"
elif matches "${DOMAIN//./[.]}[.]key" "$scheduler_secrets"; then
	fail "the key is mounted on bw-scheduler, which never opens it"
else
	ok "the key is NOT mounted on bw-scheduler, which no longer runs jobs"
fi

# --------------------------------------------------------- the service, configured by path only

log "creating the application service; the label carries a PATH, never key material"
docker service create --name "${STACK}-app" --detach \
	--network "${STACK}_bw-services" \
	--label "com.docker.stack.namespace=$STACK" \
	--label "bunkerweb.NAMESPACE=$STACK" \
	--label "bunkerweb.SERVER_NAME=${DOMAIN}" \
	--label "bunkerweb.USE_REVERSE_PROXY=yes" \
	--label "bunkerweb.REVERSE_PROXY_URL=/" \
	--label "bunkerweb.REVERSE_PROXY_HOST=http://${STACK}-app:8080" \
	--label "bunkerweb.USE_CUSTOM_SSL=yes" \
	--label "bunkerweb.CUSTOM_SSL_CERT=/run/secrets/${DOMAIN}.pem" \
	--label "bunkerweb.CUSTOM_SSL_KEY=/run/secrets/${DOMAIN}.key" \
	bunkerity/bunkerweb-hello:v1.0 >/dev/null

for _ in {1..40}; do
	matches "$DOMAIN" "$(api /services 2>/dev/null)" && break
	sleep 2
done
if matches "$DOMAIN" "$(api /services 2>/dev/null)"; then
	ok "the service reached the control plane"
else
	fail "${DOMAIN} never appeared in /services"
fi

# No key material anywhere in what the control plane stores or serves.
if matches "BEGIN .*PRIVATE KEY" "$(api /services/"$DOMAIN" 2>/dev/null)"; then
	fail "private key material is stored in the control plane"
else
	ok "the control plane holds a path, not key material"
fi

# ------------------------------------------------------- criterion 5: the instance serves it

log "criterion 5: the instance must serve the certificate whose key came from the secret"
served=0
for _ in {1..45}; do
	presented="$(echo | timeout 10 openssl s_client -connect "127.0.0.1:${HTTPS##*:}" -servername "$DOMAIN" 2>/dev/null |
		openssl x509 -noout -fingerprint -sha256 2>/dev/null || true)"
	if [ -n "$presented" ] && [ "$presented" = "$expected_fingerprint" ]; then
		served=1
		break
	fi
	sleep 4
done
if [ "$served" = "1" ]; then
	ok "criterion 5: the served certificate is the one whose key is the Swarm secret"
else
	echo "swarm-secrets: expected $expected_fingerprint" >&2
	echo "swarm-secrets: presented $presented" >&2
	docker service logs "${STACK}_bw-worker" --no-task-ids 2>&1 | grep -i "custom.cert" | tail -10 >&2 || true
	fail "criterion 5: the custom certificate is not being served"
fi

# --------------------------------------------------------------- the accepted limitation

log "documenting the accepted limitation: --secret-add restarts the worker task"
before_task="$(docker service ps "${STACK}_bw-worker" -q --filter desired-state=running | head -1)"
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj "/CN=${DOMAIN}" \
	-keyout "$workdir/key2.pem" -out "$workdir/cert2.pem" >/dev/null 2>&1
docker secret create "${DOMAIN}.key.v2" "$workdir/key2.pem" >/dev/null
docker service update --detach --secret-add "source=${DOMAIN}.key.v2,target=${DOMAIN}.key.v2" "${STACK}_bw-worker" >/dev/null

restarted=0
for _ in {1..45}; do
	after_task="$(docker service ps "${STACK}_bw-worker" -q --filter desired-state=running | head -1)"
	if [ -n "$after_task" ] && [ "$after_task" != "$before_task" ]; then
		restarted=1
		break
	fi
	sleep 2
done
# Not removed here: bw-worker still references it, and docker refuses. The teardown does it after
# `docker stack rm`.
if [ "$restarted" = "1" ]; then
	ok "rotation restarts the worker task, as designed and as documented -- not a regression"
else
	# Worth failing on: if this ever stops being true the limitation in the docs is wrong.
	fail "--secret-add did NOT restart the worker task; the documented limitation no longer holds"
fi

if [ "$failures" -ne 0 ]; then
	echo "swarm-secrets: $failures check(s) failed" >&2
	exit 1
fi
echo "swarm-secrets: all checks passed"
