#!/bin/bash
# BANS_TLS_DROP_REASONS closes the TLS handshake of a banned client instead of serving the 403 page.
# The decision is made in ssl_client_hello_by_lua, before any HTTP request exists, so a `status`
# action cannot see it: the only observable is the handshake itself (curl exit 35 or 56 when it is
# reset, 0 when it completes) and, for the 403 page, the HTTP status behind a completed one.
#
# One mode per call, because the setting under test is a configuration and the framework applies a
# configuration by restarting the stack between actions:
#
#   off              the setting is empty (the default): a ban is answered with the 403 page
#   drop             `manual` is listed: a manual ban resets the handshake, an unban restores it,
#                    and a ban whose reason is not listed still gets the 403 page
#   detect           SECURITY_MODE=detect: the drop is logged ("would drop") and the client is served
#   proxy-trusted    PROXY protocol, the runner is a trusted peer: the PROXY source is judged
#   proxy-untrusted  PROXY protocol, the runner is NOT a trusted peer: the claimed source is ignored
#
# "Served" below means a completed handshake and anything but the 403 page: whether the bare test
# service answers 200 or 404 is not what this checks.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "bans_tls_drop supports only the docker integration" >&2
	exit 1
fi
mode="${2:-}"

here="$(cd "$(dirname "$0")" && pwd)"
probe="${here}/probe.py"
scheduler="${BW_TEST_SCHEDULER:-bw-scheduler}"
instance="${BW_TEST_INSTANCE:-bunkerweb}"
api="${BW_TEST_API_URL:-http://127.0.0.1:8888}"
api_auth="${BW_TEST_API_AUTH:-admin:P@ssw0rd}"
converge_timeout=60

# Documentation addresses (RFC 5737): nothing real answers for them, and they cannot collide with
# the runner's own address.
claimed_banned="198.51.100.7"
claimed_clean="198.51.100.8"

banned=()
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

api_get() { curl -sS -u "$api_auth" "${api}$1" || true; }

fail() {
	echo "bans_tls_drop ${mode}: $*" >&2
	echo "bans_tls_drop ${mode}: instance view: $(api_get /bans/instances)" >&2
	exit 1
}

# Polls the instance view until the ban is (want=yes) or is not (want=no) enforced. The view
# answers 502 with an error payload whenever an instance is unreachable, so an absence only counts
# when the answer is well formed.
converge() {
	local ip="$1" want="$2" deadline=$((SECONDS + converge_timeout)) body
	while [ "$SECONDS" -lt "$deadline" ]; do
		body="$(api_get /bans/instances)"
		case "$body" in
		*'"status":"success"'*)
			case "$body" in
			*"\"ip\":\"${ip}\""*) [ "$want" = "yes" ] && return 0 ;;
			*) [ "$want" = "no" ] && return 0 ;;
			esac
			;;
		esac
		sleep 1
	done
	fail "the instance view never reached ban=${want} for ${ip}"
}

ban() { # ip [reason]
	local ip="$1" reason="${2:-}"
	if [ -n "$reason" ]; then
		docker exec "$scheduler" bwcli ban "$ip" -exp 3600 -reason "$reason" >/dev/null 2>&1 || fail "bwcli ban ${ip} failed"
	else
		docker exec "$scheduler" bwcli ban "$ip" -exp 3600 >/dev/null 2>&1 || fail "bwcli ban ${ip} failed"
	fi
	banned+=("$ip")
	converge "$ip" yes
}

unban() {
	docker exec "$scheduler" bwcli unban "$1" >/dev/null 2>&1 || fail "bwcli unban ${1} failed"
	converge "$1" no
}

cleanup() {
	local ip
	for ip in "${banned[@]}"; do
		docker exec "$scheduler" bwcli unban "$ip" >/dev/null 2>&1 || true
	done
}
trap cleanup EXIT

# curl: prints "<exit code> <http status>". 000 when there was no HTTP exchange.
https() {
	local code rc=0
	code="$(curl -sk --max-time 10 --resolve www.example.com:443:127.0.0.1 -o /dev/null -w '%{http_code}' https://www.example.com/)" || rc=$?
	echo "${rc} ${code:-000}"
}

expect_reset() { # label
	local result rc
	result="$(https)"
	rc="${result%% *}"
	case "$rc" in
	35 | 56) echo "bans_tls_drop ${mode}: $1 (curl exit ${rc})" ;;
	*) fail "$1: expected the handshake to be reset (curl exit 35 or 56), got: ${result}" ;;
	esac
}

expect_served() { # label
	local result code
	result="$(https)"
	code="${result#* }"
	[ "${result%% *}" = "0" ] && [ "$code" != "403" ] || fail "$1: expected a served response, got: ${result}"
	echo "bans_tls_drop ${mode}: $1 (HTTP ${code})"
}

expect_ban_page() { # label
	local result
	result="$(https)"
	[ "$result" = "0 403" ] || fail "$1: expected the 403 page behind a completed handshake, got: ${result}"
	echo "bans_tls_drop ${mode}: $1 (HTTP 403)"
}

# The PROXY client: the same handshake behind a header that claims `$1` as the source.
proxy_probe() { python3 "$probe" proxy "$1" || true; }

expect_proxy_reset() { # source label
	local out
	out="$(proxy_probe "$1")"
	case "$out" in
	RESET*) echo "bans_tls_drop ${mode}: $2 (${out})" ;;
	*) fail "$2: expected the handshake to be reset, got: ${out}" ;;
	esac
}

expect_proxy_served() { # source label
	local out
	out="$(proxy_probe "$1")"
	case "$out" in
	OK*403*) fail "$2: the 403 page was served: ${out}" ;;
	OK*) echo "bans_tls_drop ${mode}: $2 (${out})" ;;
	*) fail "$2: expected a completed handshake, got: ${out}" ;;
	esac
}

bw_logs() { docker logs --since "$started" "$instance" 2>&1 || true; }

peer="$(python3 "$probe" peer)"
echo "bans_tls_drop ${mode}: BunkerWeb sees this runner as ${peer}"

case "$mode" in
off)
	expect_served "not banned yet"
	ban "$peer"
	expect_ban_page "setting empty: a manual ban is answered with the 403 page"
	if bw_logs | grep -q "banned IP .* at the TLS ClientHello"; then
		fail "the TLS drop logged something with the setting empty"
	fi
	unban "$peer"
	expect_served "unbanned"
	;;

drop)
	expect_served "not banned yet"
	ban "$peer"
	expect_reset "manual ban: handshake reset"
	expect_reset "manual ban: still reset on a second attempt"
	unban "$peer"
	expect_served "unbanned: handshake succeeds"
	# bwcli takes free text for the reason; only the five documented ids can be listed.
	ban "$peer" "not-listed"
	expect_ban_page "ban with an unlisted reason: the 403 page, not a reset"
	unban "$peer"
	expect_served "unbanned again"
	if ! bw_logs | grep -q "dropped banned IP ${peer} (manual) at the TLS ClientHello"; then
		fail "no 'dropped banned IP ${peer} (manual)' line in the instance logs"
	fi
	;;

detect)
	ban "$peer"
	expect_served "SECURITY_MODE=detect: the banned client is served"
	if ! bw_logs | grep -q "would drop banned IP ${peer} (manual) at the TLS ClientHello"; then
		fail "no 'would drop banned IP ${peer} (manual)' line in the instance logs"
	fi
	if bw_logs | grep -q "dropped banned IP"; then
		fail "detect mode logged a real drop"
	fi
	unban "$peer"
	;;

proxy-trusted)
	# The runner connects from the Docker gateway, which REAL_IP_FROM lists, so its PROXY header is
	# believed and the ban key is the claimed source.
	expect_proxy_served "$claimed_banned" "not banned yet"
	ban "$claimed_banned"
	expect_proxy_reset "$claimed_banned" "banned PROXY source: handshake reset"
	expect_proxy_served "$claimed_clean" "clean PROXY source: handshake completes"
	# The peer's own address is not the client: banning it must not touch a clean source.
	ban "$peer"
	expect_proxy_served "$claimed_clean" "banned peer, clean PROXY source: handshake completes"
	unban "$peer"
	unban "$claimed_banned"
	expect_proxy_served "$claimed_banned" "PROXY source unbanned: handshake completes"
	;;

proxy-untrusted)
	# REAL_IP_FROM does not list the runner: the header is parsed and ignored, the client is the peer.
	ban "$claimed_banned"
	expect_proxy_served "$claimed_banned" "untrusted peer claiming a banned source: the claim is not believed"
	ban "$peer"
	expect_proxy_reset "$claimed_clean" "untrusted peer, banned peer: judged on its own address"
	unban "$peer"
	expect_proxy_served "$claimed_clean" "peer unbanned: handshake completes"
	;;

*)
	echo "usage: test.sh docker off|drop|detect|proxy-trusted|proxy-untrusted" >&2
	exit 1
	;;
esac

echo "bans_tls_drop ${mode}: all checks passed"
