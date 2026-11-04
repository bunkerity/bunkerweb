#!/bin/bash
# Redis Cluster slot migration under live traffic: the Lua client must follow ASK and MOVED.
#
# The cluster is the three-master stack of tests/misc/docker/redis-cluster.yml, already up and
# wired to BunkerWeb by the cluster_check action before this one. Two clients, both behind
# X-Forwarded-For, send requests the whole time:
#
#   banned    banned through bwcli: the ban key {<ip>} exists in the cluster, the client must stay refused
#   clean     never banned: every request looks its ban keys up in the cluster (EVAL on the slot of {<ip>}),
#             and is served when Redis errors (a failed lookup never bans), so the log scan below is what
#             proves the lookup worked
#   redisonly banned in Redis alone, by a key written straight into the cluster in the format of the ban
#             above, before the client sends its first request: the instance holds no local copy, so each
#             lookup has to be answered by the cluster, whatever state its slot is in
#
# The slots of {banned} and {clean} then move to another master the way redis-cli --cluster reshard
# does it, in three phases with traffic running through each:
#
#   migrating  SETSLOT IMPORTING + MIGRATING: keys still on the source are served there, the others
#              answer ASK
#   moved      MIGRATE the keys: the source answers ASK for them too
#   finished   SETSLOT NODE: the source answers MOVED until the client refreshes its slot map
#
# Redis counts what it rejected (INFO errorstats), so the script also checks that the ASK and MOVED
# redirections really happened, and that the client sent ASKING to the importing node. A run where
# the redirects never fire would pass the traffic checks for nothing.
#
# While a slot is being rehashed Redis answers TRYAGAIN to a multi-key command when some of its keys
# are missing, which the ban lookup is (one EVAL over every key a ban may live under). The lookup then
# reads the keys one by one, which follow ASK, so the verdict is the same as outside the move: the
# redisonly client is refused every time, and no lookup may fail on TRYAGAIN (the cluster must have
# answered some, or the run proved nothing). Any other Redis error fails the action, and so does any
# error at all once the move is over.
#
# The slots are moved back at the end: the next cluster actions assert which node holds which key.
#
# Optional second argument, --lib <file>: copy that file over the instance's rediscluster.lua and
# reload first. Used by hand to run the action with the redirection handling disabled.

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "cluster_migrate supports only the docker integration" >&2
	exit 1
fi

scheduler="${BW_TEST_SCHEDULER:-bw-scheduler}"
instance="${BW_TEST_INSTANCE:-bunkerweb}"
host="www.example.com"
# Documentation addresses (RFC 5737)
banned_ip="198.51.100.7"
clean_ip="198.51.100.8"
redis_ip="198.51.100.9"
# Redis only reads a ban from the cluster when the instance holds no copy, and keeps the copy for
# BAN_LOCAL_CACHE_TTL (30 s): every phase lasts longer, so each one has a real lookup.
phase_seconds=35

work="$(mktemp -d)"
touch "$work/traffic.log"
traffic_pid=""
banned_set=0
redis_key_set=0
deferred=()

fail() {
	echo "cluster_migrate: $*" >&2
	exit 1
}

cleanup() {
	[ -z "$traffic_pid" ] || kill "$traffic_pid" 2>/dev/null || true
	if [ "$banned_set" = 1 ]; then
		docker exec "$scheduler" bwcli unban "$banned_ip" >/dev/null 2>&1 || true
	fi
	if [ "$redis_key_set" = 1 ]; then
		docker exec redis-cluster-1 redis-cli -c del "bans_ip_{$redis_ip}" >/dev/null 2>&1 || true
	fi
	rm -rf "$work"
}
trap cleanup EXIT

rc() { # node args...
	docker exec "redis-cluster-$1" redis-cli "${@:2}"
}

# --- optional: a different client library for the instance --------------------------------------------

if [ "${2:-}" = "--lib" ]; then
	docker cp "${3:?--lib needs a file}" "$instance:/usr/share/bunkerweb/deps/lib/lua/resty/rediscluster.lua"
	docker exec "$instance" nginx -s reload
	sleep 5
	echo "cluster_migrate: running with $3"
fi

# --- topology ---------------------------------------------------------------------------------

declare -A node_id node_addr
for n in 1 2 3; do
	node_id[$n]="$(rc "$n" cluster myid)"
	node_addr[$n]="$(rc "$n" cluster nodes | awk '/myself/ {split($2, a, "[:@]"); print a[1] " " a[2]}')"
	[ -n "${node_id[$n]}" ] && [ -n "${node_addr[$n]}" ] || fail "cannot read the identity of redis-cluster-$n"
done

slot_of() { rc 1 cluster keyslot "{$1}"; }

# The 1-based node that owns the slot, from the cluster view of node 1.
owner_of() {
	local id
	id="$(rc 1 cluster nodes | awk -v s="$1" '
		$3 ~ /master/ {
			for (i = 9; i <= NF; i++) {
				if ($i ~ /^\[/) continue
				split($i, r, "-")
				lo = r[1]; hi = (r[2] == "" ? r[1] : r[2])
				if (s + 0 >= lo + 0 && s + 0 <= hi + 0) { print $1; exit }
			}
		}')"
	for n in 1 2 3; do
		[ "${node_id[$n]}" = "$id" ] && {
			echo "$n"
			return
		}
	done
	fail "no owner found for slot $1"
}

# --- traffic ----------------------------------------------------------------------------------

request() { # ip path
	curl -s -o /dev/null --max-time 5 -w '%{http_code}' --resolve "$host:80:127.0.0.1" -H "X-Forwarded-For: $1" "http://$host$2" || true
}

traffic() {
	while :; do
		for ip in "$banned_ip" "$clean_ip" "$redis_ip"; do
			echo "$(cat "$work/phase") $ip $(request "$ip" /)" >>"$work/traffic.log"
		done
		sleep 0.2
	done
}

set_phase() {
	date -u +%Y-%m-%dT%H:%M:%SZ >"$work/start-$1"
	echo "$1" >"$work/phase"
	echo "cluster_migrate: phase $1"
}

# A phase is only judged on the traffic sent while it lasted: the banned clients must have been refused
# every time, the clean one never. A failure is recorded and reported at the end, so one run prints the
# counts of every phase.
phase_check() { # phase ip expect(refused|served)
	local p="$1" ip="$2" want="$3" total bad
	total="$(grep -c "^$p $ip " "$work/traffic.log" || true)"
	if [ "$total" -lt 10 ]; then
		deferred+=("$p: only $total requests of $ip, the traffic loop is stuck")
		return
	fi
	if [ "$want" = refused ]; then
		bad="$(grep "^$p $ip " "$work/traffic.log" | grep -vc " 403\$" || true)"
	else
		bad="$(grep "^$p $ip " "$work/traffic.log" | grep -cE ' (403|000|5[0-9][0-9])$' || true)"
	fi
	if [ "$bad" != 0 ]; then
		deferred+=("$p: $ip was not $want $bad times out of $total: $(grep "^$p $ip " "$work/traffic.log" | sort | uniq -c | tr '\n' ';')")
		echo "cluster_migrate: $p: $ip $want ONLY $((total - bad))/$total times"
		return
	fi
	echo "cluster_migrate: $p: $ip $want $total/$total times"
}

check_phase() {
	phase_check "$1" "$banned_ip" refused
	phase_check "$1" "$redis_ip" refused
	phase_check "$1" "$clean_ip" served
}

# --- a ban through BunkerWeb ---------------------------------------------------------------------

docker exec "$scheduler" bwcli ban "$banned_ip" -exp 3600 >/dev/null 2>&1 || fail "bwcli ban $banned_ip failed"
banned_set=1

ban_key=""
for _ in $(seq 1 30); do
	for n in 1 2 3; do
		found="$(rc "$n" --scan --pattern "*{$banned_ip}*" || true)"
		[ -z "$found" ] || ban_key="$found"
	done
	[ -z "$ban_key" ] || break
	sleep 1
done
[ -n "$ban_key" ] || fail "no key tagged {$banned_ip} reached the cluster after the ban"
echo "cluster_migrate: the ban is in the cluster as $ban_key"

# The Redis-only ban: the value BunkerWeb wrote for the first one, under the key of the third address,
# before that address has sent a request.
ban_value="$(rc 1 -c get "$ban_key" | tr -d '\r')"
[ -n "$ban_value" ] || fail "cannot read the value of $ban_key"
rc 1 -c set "bans_ip_{$redis_ip}" "$ban_value" ex 3600 >/dev/null || fail "cannot write the Redis-only ban"
redis_key_set=1
echo "cluster_migrate: bans_ip_{$redis_ip} written straight into the cluster, value $ban_value"

# --- slots -----------------------------------------------------------------------------------

declare -A src dst
slots=()
for ip in "$banned_ip" "$clean_ip" "$redis_ip"; do
	slot="$(slot_of "$ip")"
	case " ${slots[*]:-} " in *" $slot "*) continue ;; esac
	slots+=("$slot")
	src[$slot]="$(owner_of "$slot")"
	dst[$slot]=$((src[$slot] % 3 + 1))
	echo "cluster_migrate: {$ip} is slot $slot on redis-cluster-${src[$slot]}, moving to redis-cluster-${dst[$slot]}"
done

errorstat() { # node name
	rc "$1" info errorstats | tr -d '\r' | sed -n "s/^errorstat_$2:count=\([0-9]*\).*/\1/p" | head -1
}
cmdcalls() { # node cmd
	rc "$1" info commandstats | tr -d '\r' | sed -n "s/^cmdstat_$2:calls=\([0-9]*\).*/\1/p" | head -1
}
snapshot() { # label: ASK, MOVED and TRYAGAIN errors, ASKING calls, per node (0 when Redis has not counted one yet)
	local n a m k t
	for n in 1 2 3; do
		a="$(errorstat "$n" ASK || true)"
		m="$(errorstat "$n" MOVED || true)"
		t="$(errorstat "$n" TRYAGAIN || true)"
		k="$(cmdcalls "$n" asking || true)"
		echo "$1 $n ${a:-0} ${m:-0} ${k:-0} ${t:-0}"
	done
}

# --- the migration ---------------------------------------------------------------------------

migrate_forward() {
	local s
	snapshot before >"$work/before"

	set_phase migrating
	for s in "${slots[@]}"; do
		rc "${dst[$s]}" cluster setslot "$s" importing "${node_id[${src[$s]}]}" >/dev/null
		rc "${src[$s]}" cluster setslot "$s" migrating "${node_id[${dst[$s]}]}" >/dev/null
	done
	sleep "$phase_seconds"
	check_phase migrating

	set_phase moved
	for s in "${slots[@]}"; do
		move_keys "$s"
	done
	sleep "$phase_seconds"
	check_phase moved

	set_phase finished
	for s in "${slots[@]}"; do
		finish_slot "$s"
	done
	sleep "$phase_seconds"
	check_phase finished
	snapshot after >"$work/after"
}

move_keys() { # slot
	local s="$1" keys
	while :; do
		mapfile -t keys < <(rc "${src[$s]}" cluster getkeysinslot "$s" 100 | tr -d '\r')
		[ "${#keys[@]}" -gt 0 ] && [ -n "${keys[0]}" ] || break
		# shellcheck disable=SC2086
		rc "${src[$s]}" migrate ${node_addr[${dst[$s]}]} "" 0 5000 keys "${keys[@]}" >/dev/null || fail "MIGRATE of slot $s failed"
	done
}

finish_slot() { # slot
	local s="$1" n
	for n in "${dst[$s]}" "${src[$s]}"; do
		rc "$n" cluster setslot "$s" node "${node_id[${dst[$s]}]}" >/dev/null
	done
	for n in 1 2 3; do
		[ "$n" = "${src[$s]}" ] || [ "$n" = "${dst[$s]}" ] || rc "$n" cluster setslot "$s" node "${node_id[${dst[$s]}]}" >/dev/null
	done
}

echo warmup >"$work/phase"
traffic &
traffic_pid=$!
sleep 3
set_phase baseline
sleep "$phase_seconds"
check_phase baseline

migrate_forward

# The ban key survived the move, on the new owner.
for s in "${slots[@]}"; do
	[ "$(owner_of "$s")" = "${dst[$s]}" ] || fail "slot $s is not on redis-cluster-${dst[$s]} after the move"
done
[ -n "$(rc "$(owner_of "$(slot_of "$banned_ip")")" exists "$ban_key" | grep -x 1 || true)" ] || fail "the ban key $ban_key is gone from the new owner"
echo "cluster_migrate: the ban key survived on the new owner"

# The redirections the client followed, from the nodes' own books: columns of a snapshot line are
# label, node, ASK errors, MOVED errors, ASKING calls, TRYAGAIN errors.
delta() { # column
	paste -d' ' "$work/before" "$work/after" | awk -v c="$1" '{ t += $(c + 6) - $c } END { print t + 0 }'
}
ask="$(delta 3)"
moved="$(delta 4)"
asking="$(delta 5)"
tryagain_sent="$(delta 6)"
echo "cluster_migrate: redirections answered during the move: ASK=$ask MOVED=$moved, ASKING sent to the importing node: $asking"
[ "$ask" -gt 0 ] || fail "no ASK redirection was answered: the migrating phase never reached the client"
[ "$asking" -gt 0 ] || fail "the client never sent ASKING to the importing node"
[ "$moved" -gt 0 ] || fail "no MOVED redirection was answered: the client never used a stale slot map"
echo "cluster_migrate: multi-key commands answered TRYAGAIN by the cluster during the move: $tryagain_sent"
[ "$tryagain_sent" -gt 0 ] || fail "the cluster never answered TRYAGAIN: the ban lookups did not meet a rehashing slot"

# The instance logs. A Redis error shows as "redis call error", "redis script error" or "can't connect
# to redis" on the lookups, or as "falling back to local" on the counters.
redis_errors="redis (call|script) error|can't connect to redis|redis_(increase|decrease) failed"
logs() { docker logs --since "$1" ${2:+--until "$2"} "$instance" 2>&1 | grep -iE "$redis_errors" || true; }

# Nothing is tolerated in the log, TRYAGAIN included: a lookup that failed on it served its request unjudged.
other="$(logs "$(cat "$work/start-baseline")" | grep -vi "TRYAGAIN" || true)"
if [ -n "$other" ]; then
	echo "cluster_migrate: Redis errors that are not TRYAGAIN:" >&2
	echo "$other" | sed 's/, client: .*//' | sort | uniq -c | head -20 >&2
	fail "the instance logged Redis errors during the move"
fi
tryagain="$(logs "$(cat "$work/start-migrating")" | grep -ci "TRYAGAIN" || true)"
echo "cluster_migrate: ban lookups and Redis calls that failed on TRYAGAIN while the slots were rehashing: $tryagain"
[ "$tryagain" = 0 ] || deferred+=("$tryagain Redis calls of the instance failed on TRYAGAIN")

# Once the move is over, and the first seconds of it have passed, there is no error at all.
settled="$(date -u -d "$(cat "$work/start-finished") + 5 seconds" +%Y-%m-%dT%H:%M:%SZ)"
late="$(logs "$settled")"
if [ -n "$late" ]; then
	echo "$late" | sed 's/, client: .*//' | sort | uniq -c | head -20 >&2
	fail "the instance logged Redis errors after the move was over"
fi
echo "cluster_migrate: no Redis error before the move and none from 5 s after it"

# Back to the original owners.
for s in "${slots[@]}"; do
	tmp="${src[$s]}"
	src[$s]="${dst[$s]}"
	dst[$s]="$tmp"
	rc "${dst[$s]}" cluster setslot "$s" importing "${node_id[${src[$s]}]}" >/dev/null
	rc "${src[$s]}" cluster setslot "$s" migrating "${node_id[${dst[$s]}]}" >/dev/null
	move_keys "$s"
	finish_slot "$s"
done
echo "cluster_migrate: slots back on their first owners"

if [ "${#deferred[@]}" -gt 0 ]; then
	printf 'cluster_migrate: FAILED: %s\n' "${deferred[@]}" >&2
	exit 1
fi

echo "cluster_migrate: all checks passed"
