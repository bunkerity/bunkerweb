#!/bin/bash
# Reads the rendered global CRS host rules inside the instance and checks the chunking.
#
# Usage: check-rendered.sh <container>
#
# Why a file check on top of the HTTP probes: the marker for the UI IP-literal list sets
# tx.bw_ui_ip_host, which only rule 9802111 reads, and that rule removes CRS 920350 (a warning that
# never reaches the anomaly threshold alone), so no request tells it apart. Reading the rendered file
# is the one way to see that list was chunked and that its last entry landed in a rule.

CONTAINER="${1:?container name}"
UI_FILE="/etc/nginx/http/ui.modsec-crs"
BOT_FILE="/etc/nginx/http/antibot.modsec-crs"
IP_FILE="/etc/nginx/http/ip-host.modsec-crs"
# The templates cap an @rx operand at 8,192 bytes. A line also carries the rule's own text, so allow
# 9,000; before the fix one line held every host (60 KB and more).
MAX_LINE=9000

fail() {
    echo "modsecurity_global_crs_large_host_lists: FAIL: $*"
    exit 1
}

count() { # <file> <fixed string>
    docker exec "$CONTAINER" grep -c -F -- "$2" "$1" 2> /dev/null
}

longest() { # <file>
    docker exec "$CONTAINER" awk '{ if (length($0) > max) max = length($0) } END { print max + 0 }' "$1"
}

for file in "$UI_FILE" "$BOT_FILE" "$IP_FILE"; do
    docker exec "$CONTAINER" test -s "$file" || fail "$file is missing or empty"
    len="$(longest "$file")"
    [ "$len" -le "$MAX_LINE" ] || fail "$file has a line of $len bytes, over $MAX_LINE"
    echo "modsecurity_global_crs_large_host_lists: $file longest line $len bytes"
done

ui_markers="$(count "$UI_FILE" "setvar:tx.bw_ui_host=1")"
ip_markers="$(count "$UI_FILE" "setvar:tx.bw_ui_ip_host=1")"
bot_markers="$(count "$BOT_FILE" "setvar:tx.bw_antibot_host=1")"
ip_host_markers="$(count "$IP_FILE" "setvar:tx.bw_ip_host=1")"
echo "modsecurity_global_crs_large_host_lists: markers ui=$ui_markers ui_ip=$ip_markers antibot=$bot_markers ip_host=$ip_host_markers"

# 1,500 names are far past one chunk (about 40 KB of regex), 1,000 IP literals too (about 14 KB).
[ "${ui_markers:-0}" -ge 2 ] || fail "UI name list was not chunked into marker rules"
[ "${ip_markers:-0}" -ge 2 ] || fail "UI IP list was not chunked into marker rules"
[ "${bot_markers:-0}" -ge 2 ] || fail "antibot list was not chunked into marker rules"
[ "${ip_host_markers:-0}" -ge 2 ] || fail "the global IP host list was not chunked into marker rules"

# The last entry of every list must have landed in a rule, not been cut off at the chunk limit.
[ "$(count "$UI_FILE" 'u1500\.ui\.example\.com')" -ge 1 ] || fail "last UI name is not in the rendered rules"
[ "$(count "$UI_FILE" '10\.77\.3\.250')" -ge 1 ] || fail "last UI IP literal is not in the rendered rules"
[ "$(count "$BOT_FILE" 'b1500\.bot\.example\.com')" -ge 1 ] || fail "last antibot name is not in the rendered rules"
[ "$(count "$IP_FILE" '10\.77\.3\.250')" -ge 1 ] || fail "last IP literal is not in the rendered global IP host rules"

# The exception rules test the markers; the old one-regex link must be gone.
[ "$(count "$UI_FILE" 'SecRule TX:bw_ui_host "@eq 1"')" -ge 1 ] || fail "UI rules do not test tx.bw_ui_host"
[ "$(count "$UI_FILE" 'SecRule TX:bw_ui_ip_host "@eq 1"')" -ge 1 ] || fail "the IP rule does not test tx.bw_ui_ip_host"
[ "$(count "$BOT_FILE" 'SecRule TX:bw_antibot_host "@eq 1"')" -ge 1 ] || fail "the antibot allow rule does not test tx.bw_antibot_host"
[ "$(count "$IP_FILE" 'SecRule TX:bw_ip_host "@eq 1"')" -ge 1 ] || fail "the global IP host rule does not test tx.bw_ip_host"

echo "modsecurity_global_crs_large_host_lists: all checks passed"
