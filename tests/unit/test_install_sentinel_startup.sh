#!/bin/bash
# With KEEP_CONFIG_ON_RESTART=yes, startup keeps the preserved tree unless the install sentinel says the
# last install was cut short. The temporary-config block of each startup script is cut out and run against
# a scratch root with a stub generator.
#
# Run: bash tests/unit/test_install_sentinel_startup.sh
#      ENTRYPOINT=/other/entrypoint.sh START=/other/start.sh bash tests/unit/test_install_sentinel_startup.sh

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
entrypoint="${ENTRYPOINT:-$repo/src/bw/entrypoint.sh}"
start="${START:-$repo/src/linux/scripts/start.sh}"
failed=0
checks=0

# usage: extract <file> <text of the first line> <text of the last line>   (both lines excluded)
extract() {
	awk -v from="$2" -v to="$3" '
		!on && index($0, from) { on = 1; next }
		on && index($0, to) { exit }
		on { print }
	' "$1"
}

# usage: run_case <name> <script|entrypoint> <keep> <sentinel yes|no> <generator rc>
# Sets $out (what the block printed), $rc, and leaves the scratch root in $T.
run_case() {
	local kind="$2" keep="$3" sentinel="$4" gen_rc="$5" block env_path
	T="$(mktemp -d)"
	mkdir -p "$T/bin" "$T/etc/nginx" "$T/var/tmp/bunkerweb" "$T/tmp"
	printf '#!/bin/sh\ntouch "%s/generator.ran"\nexit %s\n' "$T" "$gen_rc" >"$T/bin/python3"
	chmod +x "$T/bin/python3"
	if [ "$kind" = entrypoint ]; then
		block="$(extract "$entrypoint" '# generate "temp" config' '# Clean orphaned NGINX temp files')"
		env_path="$T/tmp/variables.env"
	else
		block="$(extract "$start" 'tmp_env_content="$(generate_tmp_env_content)"' '# Clean orphaned NGINX temp files')"
		env_path="$T/var/tmp/bunkerweb/tmp.env"
	fi
	[ -n "$block" ] || { echo "cannot extract the block from the $kind script"; return 1; }
	: >"$env_path"
	[ "$sentinel" = yes ] && : >"$T/etc/nginx/.bw-install-incomplete"
	block="$(printf '%s\n' "$block" | sed -e 's#/var/tmp#@T@/var/tmp#g' -e 's#/etc/nginx#@T@/etc/nginx#g' -e 's#"/tmp/variables.env"#"@T@/tmp/variables.env"#g')"
	block="${block//@T@/$T}"
	out="$(
		PATH="$T/bin:$PATH" KEEP_CONFIG_ON_RESTART="$keep" PYTHON_BIN="$T/bin/python3" BW_PYTHONPATH="" bash -c '
			log() { echo "LOG $*"; }
			generate_tmp_env_content() { echo "IS_LOADING=yes"; }
			write_tmp_env_file() { printf "%s\n" "$2" >"$1"; }
			run_as_nginx() { "$@"; }
			'"$block"'
			echo "BLOCK-DONE"
		' 2>&1
	)"
	rc=$?
}

check() { # check <name> <condition result 0|1>
	checks=$((checks + 1))
	if [ "$2" -eq 0 ]; then
		echo "ok   $1"
	else
		echo "FAIL $1"
		echo "     rc=$rc out=$(printf '%s' "$out" | tr '\n' '|')"
		echo "     root: $(cd "$T" && find . -type f | sort | tr '\n' ' ')"
		failed=$((failed + 1))
	fi
}

ran() { [ -e "$T/generator.ran" ]; }
sentinel_present() { [ -e "$T/etc/nginx/.bw-install-incomplete" ]; }
needs_config() { [ -e "$T/var/tmp/bunkerweb_needs_config" ]; }

for kind in entrypoint script; do
	run_case "" "$kind" yes no 0
	check "$kind: KEEP=yes without sentinel keeps the tree" "$(! ran && needs_config && echo 0 || echo 1)"
	rm -rf "$T"

	run_case "" "$kind" yes yes 0
	check "$kind: KEEP=yes with sentinel regenerates" "$(ran && echo 0 || echo 1)"
	check "$kind: KEEP=yes with sentinel warns" "$(grep -q 'interrupted' <<<"$out" && echo 0 || echo 1)"
	check "$kind: KEEP=yes with sentinel clears the sentinel after success" "$(! sentinel_present && echo 0 || echo 1)"
	check "$kind: KEEP=yes with sentinel does not ask for a config push" "$(! needs_config && echo 0 || echo 1)"
	rm -rf "$T"

	run_case "" "$kind" no yes 0
	check "$kind: KEEP=no with sentinel regenerates and clears it" "$(ran && ! sentinel_present && echo 0 || echo 1)"
	rm -rf "$T"

	run_case "" "$kind" yes yes 1
	check "$kind: failed regeneration refuses to go on" "$([ "$rc" -ne 0 ] && ! grep -q BLOCK-DONE <<<"$out" && echo 0 || echo 1)"
	check "$kind: failed regeneration keeps the sentinel" "$(sentinel_present && echo 0 || echo 1)"
	rm -rf "$T"
done

echo "checks=$checks failed=$failed"
[ "$failed" -eq 0 ]
