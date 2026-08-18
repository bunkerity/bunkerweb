#!/bin/bash

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "internalcert supports only the docker integration" >&2
	exit 1
fi

# The monorepo harness builds this tag (tests/scripts/build.sh); the standalone default the
# external repo used does not exist here.
image="${BW_TEST_IMAGE:-bunkerity/bunkerweb:tests}"
suffix="$$-${RANDOM}"
container="internalcert-${suffix}"
volume="internalcert-${suffix}"

cleanup() {
	docker rm -f "$container" >/dev/null 2>&1 || true
	docker volume rm "$volume" >/dev/null 2>&1 || true
}

fail() {
	docker logs "$container" 2>/dev/null || true
	echo "internalcert: $*" >&2
	exit 1
}

wait_until_healthy() {
	local state
	for _ in {1..90}; do
		state="$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || true)"
		[ "$state" = "healthy" ] && return
		[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" = "true" ] || break
		sleep 1
	done
	fail "container did not become healthy"
}

assert_tls13() {
	local port="$1"
	local server_name="$2"
	local output
	if ! output="$(docker exec "$container" bash -c \
		"timeout 10 openssl s_client -connect 127.0.0.1:${port} -servername ${server_name} -tls1_3 -brief </dev/null 2>&1")"; then
		fail "TLS handshake failed on port ${port}"
	fi
	echo "$output" | grep -q "Protocol version: TLSv1.3" || fail "port ${port} did not negotiate TLS 1.3"
}

served_fingerprint() {
	local port="$1"
	local server_name="$2"
	docker exec "$container" bash -c \
		"set -o pipefail; timeout 10 openssl s_client -connect 127.0.0.1:${port} -servername ${server_name} -tls1_3 -showcerts </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
}

disk_fingerprint() {
	docker exec "$container" openssl x509 -in "$1" -noout -fingerprint -sha256
}

trap cleanup EXIT
docker volume create "$volume" >/dev/null
docker run -d \
	--name "$container" \
	--volume "${volume}:/data" \
	--env API_LISTEN_HTTP=no \
	--env API_LISTEN_HTTPS=yes \
	"$image" >/dev/null

wait_until_healthy
assert_tls13 8443 www.example.org
assert_tls13 5443 bwapi

[ "$(served_fingerprint 8443 www.example.org)" = "$(disk_fingerprint /var/lib/bunkerweb/default-server-cert.pem)" ] \
	|| fail "default-server served certificate differs from disk"
[ "$(served_fingerprint 5443 bwapi)" = "$(disk_fingerprint /var/lib/bunkerweb/api-server-cert.pem)" ] \
	|| fail "API served certificate differs from disk"

before="$(docker exec "$container" sha256sum \
	/var/lib/bunkerweb/default-server-cert.pem \
	/var/lib/bunkerweb/default-server-cert.key \
	/var/lib/bunkerweb/api-server-cert.pem \
	/var/lib/bunkerweb/api-server-cert.key)"

docker restart "$container" >/dev/null
wait_until_healthy

after="$(docker exec "$container" sha256sum \
	/var/lib/bunkerweb/default-server-cert.pem \
	/var/lib/bunkerweb/default-server-cert.key \
	/var/lib/bunkerweb/api-server-cert.pem \
	/var/lib/bunkerweb/api-server-cert.key)"
[ "$before" = "$after" ] || fail "certificate material changed after restart"

assert_tls13 8443 www.example.org
assert_tls13 5443 bwapi
if docker exec "$container" curl --fail --silent --max-time 5 http://127.0.0.1:5443/ >/dev/null 2>&1; then
	fail "API HTTPS port accepted plaintext HTTP"
fi

echo "internalcert: all checks passed"
