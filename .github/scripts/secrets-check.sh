#!/usr/bin/env bash
# Check a CICD_SECRETS env file (and optionally the candidate that replaces it) before it is uploaded.
#
#   bash secrets-check.sh --live <file> [--next <file>] [--domains-dir <dir>] [--no-terraform] [--no-remote]
#
# Exit codes: 0 no FAIL, 1 at least one FAIL, 2 usage error. A WARN never fails the run.
#
# Values never leave this process. Output is variable names, statuses, counts, zones, regions and
# dates. Files are sourced in a clean `env -i` child, every tool writes to private temp files, and
# stderr is discarded. Only read-only calls are made: scw get/list, GitHub GET, dig, and
# terraform init + `plan -refresh=false -lock=false` without state.
# --no-remote skips scw, dig, curl and terraform (terraform init downloads the providers).
set -Eeuo pipefail

usage() {
	cat >&2 <<-'EOF'
		usage: secrets-check.sh --live <file> [--next <file>] [--domains-dir <dir>] [--no-terraform] [--no-remote]
	EOF
	exit 2
}

LIVE="" NEXT="" DOMAINS_DIR="" NO_TF=0 NO_REMOTE=0
while (($#)); do
	case $1 in
	--live) [[ $# -ge 2 ]] || usage; LIVE=$2; shift 2 ;;
	--next) [[ $# -ge 2 ]] || usage; NEXT=$2; shift 2 ;;
	--domains-dir) [[ $# -ge 2 ]] || usage; DOMAINS_DIR=$2; shift 2 ;;
	--no-terraform) NO_TF=1; shift ;;
	--no-remote) NO_REMOTE=1; shift ;;
	*) usage ;;
	esac
done
[[ -n $LIVE && -f $LIVE && -r $LIVE ]] || usage
[[ -z $NEXT || (-f $NEXT && -r $NEXT) ]] || usage
[[ -z $DOMAINS_DIR || -d $DOMAINS_DIR ]] || usage
LIVE=$(realpath "$LIVE")
[[ -z $NEXT ]] || NEXT=$(realpath "$NEXT")
[[ -z $DOMAINS_DIR ]] || DOMAINS_DIR=$(realpath "$DOMAINS_DIR")
((BASH_VERSINFO[0] >= 5 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4))) || usage

# Nothing below may reach stderr: bash and the tools can quote values in their messages.
exec 2>/dev/null
LC_ALL=C
export LC_ALL

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
umask 077
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/home" "$T/load"

CNT_PASS=0 CNT_WARN=0 CNT_FAIL=0
emit() {
	local status=$1
	shift
	# Last line of defence: a line that carries a loaded value is replaced, whatever produced it.
	if leaks "$status $*"; then
		status=FAIL
		set -- leak-guard "an output line carried a loaded value and was withheld"
	fi
	case $status in
	PASS) CNT_PASS=$((CNT_PASS + 1)) ;;
	WARN) CNT_WARN=$((CNT_WARN + 1)) ;;
	FAIL) CNT_FAIL=$((CNT_FAIL + 1)) ;;
	esac
	printf '%s %s\n' "$status" "$*"
}
trap 'emit FAIL internal-error "line $LINENO"; printf "INFO summary pass=%s warn=%s fail=%s\n" "$CNT_PASS" "$CNT_WARN" "$CNT_FAIL"; exit 1' ERR

# ----------------------------------------------------------------------------------------------
# Loading: source each file in a clean child, return name/flag/value triples through a NUL stream.
# ----------------------------------------------------------------------------------------------
# shellcheck disable=SC2016
LOADER='
set +e +u
__sc_file=$1 __sc_out=$2 __sc_so=$3 __sc_se=$4
__sc_rc=x
declare -A __sc_pv=() __sc_pf=()
# Names bash itself updates, or that a file legitimately moves (cd, getopts): not compared.
__sc_skip() { case $1 in __sc_* | _ | BASH* | EPOCH* | RANDOM | SRANDOM | SECONDS | HISTCMD | PIPESTATUS | FUNCNAME | GROUPS | DIRSTACK | LINENO | PWD | OLDPWD | SHLVL | OPTIND | SHELLOPTS) return 0 ;; esac; return 1; }
# Builtins only past this point: a file that overrides PATH must not stop the dump.
while IFS= read -r __sc_n; do
	[[ $__sc_n =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
	__sc_f=-
	[[ ${!__sc_n@a} == *x* ]] && __sc_f=x
	__sc_pv[$__sc_n]=${!__sc_n}
	__sc_pf[$__sc_n]=$__sc_f
done < <(compgen -v)
__sc_dump() {
	local __sc_n __sc_f
	printf "%s" "$__sc_rc" >"$__sc_out.rc"
	{
		while IFS= read -r __sc_n; do
			[[ $__sc_n =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
			__sc_skip "$__sc_n" && continue
			[[ -n ${__sc_pf[$__sc_n]+x} ]] && continue
			__sc_f=-
			[[ ${!__sc_n@a} == *x* ]] && __sc_f=x
			printf "%s\0%s\0%s\0" "$__sc_n" "$__sc_f" "${!__sc_n}"
		done < <(compgen -v)
		# A name that existed before the file ran and changed value or export flag, or was unset: the name only.
		for __sc_n in "${!__sc_pv[@]}"; do
			__sc_skip "$__sc_n" && continue
			__sc_f=-
			[[ ${!__sc_n@a} == *x* ]] && __sc_f=x
			if [[ ! -v $__sc_n || ${!__sc_n} != "${__sc_pv[$__sc_n]}" || $__sc_f != "${__sc_pf[$__sc_n]}" ]]; then
				printf "%s\0r\0\0" "$__sc_n"
			fi
		done
	} >"$__sc_out"
}
trap __sc_dump EXIT
. "$__sc_file" >"$__sc_so" 2>"$__sc_se" </dev/null
__sc_rc=$?
'

declare -A VAL EXP NAMES RESERVED SYNTAX SRC_RC SRC_OUT SRC_ERR
declare -a SECRETS=()
# Public configuration, not secret: masking them would blank the zones and the account in the output.
EXEMPT=" SCW_DEFAULT_REGION SCW_DEFAULT_ZONE TF_VAR_k8s_region GITHUB_ACCOUNT "

load_env() {
	local L=$1 file=$2 out="$T/load/$1.nul" n f v names="" reserved=""
	if ! bash -n "$file" >/dev/null 2>&1; then
		SYNTAX[$L]=bad
		return 0
	fi
	SYNTAX[$L]=ok
	(cd "$T/load" && env -i PATH="$PATH" HOME="$T/home" bash -c "$LOADER" _ "$file" "$out" "$out.so" "$out.se") >/dev/null 2>&1 || true
	SRC_RC[$L]=$(cat "$out.rc" 2>/dev/null || echo none)
	SRC_OUT[$L]=$(wc -c <"$out.so" | tr -d ' ')
	SRC_ERR[$L]=$(wc -c <"$out.se" | tr -d ' ')
	if [[ -f $out ]]; then
		while IFS= read -r -d '' n && IFS= read -r -d '' f && IFS= read -r -d '' v; do
			if [[ $f == r ]]; then
				reserved+="$n "
				continue
			fi
			VAL[$L:$n]=$v
			EXP[$L:$n]=$f
			names+="$n "
		done <"$out"
	fi
	NAMES[$L]=$names
	RESERVED[$L]=$reserved
}

has() { [[ -n ${EXP[$1:$2]+x} ]]; }
val() { printf '%s' "${VAL[$1:$2]-}"; }

# ----------------------------------------------------------------------------------------------
# Domains files: TEST_DOMAINS_<TYPE> holds whitespace separated TEST_DOMAIN<n>[_<m>]=<domain>.
# ----------------------------------------------------------------------------------------------
declare -A DOM_BAD DOM_COUNT
DOM_KEYS=() # "<file>/<name>"
declare -A DOM_VAL
DOM_FILES=()
declare -a DOM_RAW=()
load_domains() {
	[[ -n $DOMAINS_DIR ]] || return 0
	local f base tok name value bad
	for f in "$DOMAINS_DIR"/TEST_DOMAINS_*; do
		[[ -f $f ]] || continue
		base=$(basename "$f")
		DOM_FILES+=("$base")
		bad=0
		local toks=()
		read -r -a toks < <(tr -s '[:space:]' ' ' <"$f") || true
		for tok in "${toks[@]}"; do
			DOM_RAW+=("$tok" "${tok#*=}")
			name=${tok%%=*}
			value=${tok#*=}
			if [[ $tok != *=* ]] || ! [[ $name =~ ^TEST_DOMAIN[0-9]+(_[0-9]+)?$ ]]; then
				bad=$((bad + 1))
				continue
			fi
			value=${value#\*.}
			DOM_RAW+=("$value")
			if ! [[ $value =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ && $value == *.* ]]; then
				bad=$((bad + 1))
				continue
			fi
			DOM_KEYS+=("$base/$name")
			DOM_VAL[$base/$name]=$value
		done
		DOM_BAD[$base]=$bad
		DOM_COUNT[$base]=${#toks[@]}
	done
}

# TEST_DOMAIN names each integration reads, from tests/main.py: docker, autoconf and linux
# lines 59-63, kubernetes lines 67-71. staging-tests.yml:164 picks one secret per type and
# .github/scripts/release_integration.py:84-87 rejects an empty assignment. Swarm (main.py:75-79)
# has no secret in staging.yml:162-165.
domain_required() { # file -> required names
	case $1 in
	*_DOCKER | *_AUTOCONF | *_LINUX) printf 'TEST_DOMAIN1 TEST_DOMAIN1_1 TEST_DOMAIN1_2 TEST_DOMAIN1_3' ;;
	*_KUBERNETES) printf 'TEST_DOMAIN1 TEST_DOMAIN1_2 TEST_DOMAIN2 TEST_DOMAIN3' ;;
	esac
}

check_domains() {
	[[ -n $DOMAINS_DIR ]] || return 0
	local f key name req have missing
	for f in "${DOM_FILES[@]}"; do
		if [[ ${DOM_COUNT[$f]} == 0 ]]; then
			emit FAIL domains-format "$f is empty"
		elif [[ ${DOM_BAD[$f]} == 0 ]]; then
			emit PASS domains-format "$f"
		else
			emit FAIL domains-format "$f ${DOM_BAD[$f]} token(s) are not TEST_DOMAIN<n>=<domain>"
		fi
		req=$(domain_required "$f")
		[[ -n $req ]] || continue
		have=" "
		for key in "${DOM_KEYS[@]}"; do [[ ${key%%/*} == "$f" ]] && have+="${key#*/} "; done
		missing=0
		for name in $req; do
			[[ $have == *" $name "* ]] || { missing=$((missing + 1)); emit FAIL domains-required "$f missing $name"; }
		done
		((missing > 0)) || emit PASS domains-required "$f has every name the tests read"
		for name in $have; do
			[[ " $req " == *" $name "* ]] || emit INFO domains-extra "$f $name is not read by the tests"
		done
	done
}

# ----------------------------------------------------------------------------------------------
# Masking (CI only) and the output scrubber.
# ----------------------------------------------------------------------------------------------
mask_one() {
	local v=$1 line
	((${#v} >= 4)) || return 0
	SECRETS+=("$v")
	[[ ${GITHUB_ACTIONS:-} == true ]] || return 0
	local e=${v//'%'/%25}
	e=${e//$'\r'/%0D}
	e=${e//$'\n'/%0A}
	printf '::add-mask::%s\n' "$e"
	if [[ $v == *$'\n'* ]]; then
		while IFS= read -r line || [[ -n $line ]]; do
			line=${line%$'\r'}
			((${#line} >= 4)) || continue
			e=${line//'%'/%25}
			printf '::add-mask::%s\n' "$e"
		done <<<"$v"
	fi
}

mask_all() {
	local L n v el
	for L in "${LABELS[@]}"; do
		[[ ${SYNTAX[$L]} == ok ]] || continue
		for n in ${NAMES[$L]}; do
			[[ $EXEMPT == *" $n "* ]] && continue
			v=${VAL[$L:$n]}
			mask_one "$v"
			if [[ $n == TF_VAR_swarm_ips || $n == TF_VAR_swarm_ips_id ]]; then
				while IFS= read -r el; do mask_one "$el"; done < <(printf '%s' "$v" | jq -r '.[]? | strings' 2>/dev/null || true)
			fi
		done
	done
	for v in "${DOM_RAW[@]}"; do mask_one "$v"; done
}

# True when the text contains a loaded value: such text is never printed.
leaks() {
	local s v
	s=$1
	for v in "${SECRETS[@]}"; do
		((${#v} >= 6)) && [[ $s == *"$v"* ]] && return 0
	done
	return 1
}

# Terraform output can quote any value, so none of its text is printed: the log is only matched against
# these literal titles, and the label printed is the one from this list.
TF_TITLES=("Invalid value for input variable" "Invalid value for variable" "No value for required variable" "Invalid function argument"
	"Error in function call" "Unsupported argument" "Failed to query available provider packages" "Failed to install provider"
	"Inconsistent dependency lock file" "Invalid provider configuration")
tf_category() { # logfile -> one label from TF_TITLES, else uncategorised
	local t
	for t in "${TF_TITLES[@]}"; do
		if grep -qF -- "$t" "$1" 2>/dev/null; then printf '%s' "$t"; return 0; fi
	done
	printf 'uncategorised'
}

# ----------------------------------------------------------------------------------------------
# Format helpers. They return a status and never print the value.
# ----------------------------------------------------------------------------------------------
OCT='(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])'
is_ipv4() { [[ $1 =~ ^($OCT\.){3}$OCT$ ]]; }
UUID='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
ZONE_RE='(fr-par|nl-ams|pl-waw)-[1-3]'
is_uuid() { [[ $1 =~ ^(${ZONE_RE}/)?$UUID$ ]]; }
is_zone() { [[ $1 =~ ^$ZONE_RE$ ]]; }
is_region() { [[ $1 =~ ^(fr-par|nl-ams|pl-waw)$ ]]; }
id_uuid() { printf '%s' "${1##*/}"; }
# Zone for a reserved IP id: id prefix, else SCW_DEFAULT_ZONE, else fr-par-1.
id_zone() { # label id
	if [[ $2 == */* ]]; then printf '%s' "${2%%/*}"; return; fi
	local z
	z=$(val "$1" SCW_DEFAULT_ZONE)
	if is_zone "$z"; then printf '%s' "$z"; else printf 'fr-par-1'; fi
}
k8s_region() {
	local r
	r=$(val "$1" TF_VAR_k8s_region)
	[[ -n $r ]] || r=$(val "$1" SCW_DEFAULT_REGION)
	[[ -n $r ]] || r=fr-par
	printf '%s' "$r"
}

TYPES=(docker autoconf linux)
IPNAMES=(TF_VAR_docker_ip TF_VAR_autoconf_ip TF_VAR_linux_ip TF_VAR_k8s_ip)
REQUIRED=(TF_VAR_docker_ip TF_VAR_docker_ip_id TF_VAR_autoconf_ip TF_VAR_autoconf_ip_id TF_VAR_linux_ip TF_VAR_linux_ip_id
	TF_VAR_swarm_ips TF_VAR_swarm_ips_id TF_VAR_k8s_ip GITHUB_TOKEN GITHUB_ACCOUNT SCW_ACCESS_KEY SCW_SECRET_KEY)

# Swarm list elements into the array named by $3, or return 1 when the value is not a JSON string array.
swarm_list() { # label name arrayname
	local -n arr=$3
	local v
	v=$(val "$1" "$2")
	printf '%s' "$v" | jq -e 'type == "array" and all(.[]; type == "string")' >/dev/null 2>&1 || return 1
	# shellcheck disable=SC2034
	mapfile -t arr < <(printf '%s' "$v" | jq -r '.[]')
}

# ----------------------------------------------------------------------------------------------
# Structure checks
# ----------------------------------------------------------------------------------------------
check_structure() {
	local L=$1 n v exported=0 total=0 bad=0 i
	if [[ ${SYNTAX[$L]} != ok ]]; then
		emit FAIL syntax "[$L] bash -n rejected the file, it was not sourced"
		return 0
	fi
	emit PASS syntax "[$L]"
	if [[ ${SRC_OUT[$L]} != 0 || ${SRC_ERR[$L]} != 0 ]]; then
		emit WARN source-output "[$L] sourcing wrote stdout=${SRC_OUT[$L]}B stderr=${SRC_ERR[$L]}B"
	else
		emit PASS source-output "[$L] sourcing is silent"
	fi
	if [[ ${SRC_RC[$L]} == none ]]; then
		emit FAIL load "[$L] the loader did not run, nothing below is meaningful"
	elif [[ ${SRC_RC[$L]} == x ]]; then
		emit WARN source-status "[$L] the file ended the shell (exit or crash) while being sourced"
	elif [[ ${SRC_RC[$L]} != 0 ]]; then
		emit WARN source-status "[$L] the last command of the file returned non-zero"
	fi

	for n in ${RESERVED[$L]}; do
		emit FAIL reserved "$n [$L] the file overrides a loader-reserved name"
	done
	for n in ${NAMES[$L]}; do
		total=$((total + 1))
		if [[ ${EXP[$L:$n]} == x ]]; then
			exported=$((exported + 1))
		else
			bad=$((bad + 1))
			emit FAIL export "$n [$L] set but not exported: tests/create.sh sources it without set -a, so it never reaches terraform"
		fi
	done
	((bad > 0)) || emit PASS export "[$L] all $total variables exported"

	for n in "${REQUIRED[@]}"; do
		if ! has "$L" "$n"; then
			emit FAIL required "$n [$L] missing"
		elif [[ -z $(val "$L" "$n") ]]; then
			emit FAIL required "$n [$L] empty"
		fi
	done
	for n in SCW_DEFAULT_PROJECT_ID SCW_DEFAULT_ORGANIZATION_ID; do
		if has "$L" "$n" && [[ -n $(val "$L" "$n") ]]; then
			emit INFO scw-default "$n [$L] present"
		else
			emit WARN scw-default "$n [$L] absent (the provider docs mark it mandatory)"
		fi
	done
	for n in SCW_DEFAULT_REGION SCW_DEFAULT_ZONE; do
		if has "$L" "$n"; then
			v=$(val "$L" "$n")
			if [[ $n == *REGION ]] && is_region "$v"; then
				emit INFO scw-default "$n [$L] = $v"
			elif [[ $n == *ZONE ]] && is_zone "$v"; then
				emit INFO scw-default "$n [$L] = $v"
			else
				emit FAIL format "$n [$L] not a Scaleway region/zone"
			fi
		fi
	done

	[[ $(val "$L" SCW_ACCESS_KEY) =~ ^SCW[A-Z0-9]{17}$ ]] || ! has "$L" SCW_ACCESS_KEY || emit WARN format "SCW_ACCESS_KEY [$L] unusual shape"
	[[ $(val "$L" SCW_SECRET_KEY) =~ ^$UUID$ ]] || ! has "$L" SCW_SECRET_KEY || emit WARN format "SCW_SECRET_KEY [$L] unusual shape"
	for n in SCW_DEFAULT_PROJECT_ID SCW_DEFAULT_ORGANIZATION_ID; do
		[[ $(val "$L" "$n") =~ ^$UUID$ ]] || ! has "$L" "$n" || [[ -z $(val "$L" "$n") ]] || emit WARN format "$n [$L] not a UUID"
	done
	if has "$L" GITHUB_ACCOUNT && ! [[ $(val "$L" GITHUB_ACCOUNT) =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
		emit FAIL format "GITHUB_ACCOUNT [$L] not a GitHub login"
	fi

	for n in "${IPNAMES[@]}"; do
		has "$L" "$n" || continue
		if is_ipv4 "$(val "$L" "$n")"; then emit PASS format "$n [$L] IPv4"; else emit FAIL format "$n [$L] not an IPv4 address"; fi
	done
	for n in TF_VAR_docker_ip_id TF_VAR_autoconf_ip_id TF_VAR_linux_ip_id; do
		has "$L" "$n" || continue
		if is_uuid "$(val "$L" "$n")"; then emit PASS format "$n [$L] UUID"; else emit FAIL format "$n [$L] not a UUID (optionally zone-prefixed)"; fi
	done

	local ips=() ids=()
	if has "$L" TF_VAR_swarm_ips; then
		if swarm_list "$L" TF_VAR_swarm_ips ips; then emit PASS format "TF_VAR_swarm_ips [$L] JSON string array of ${#ips[@]}"; else ips=(); emit FAIL format "TF_VAR_swarm_ips [$L] not a JSON array of strings"; fi
	fi
	if has "$L" TF_VAR_swarm_ids || has "$L" TF_VAR_swarm_ips_id; then
		if swarm_list "$L" TF_VAR_swarm_ips_id ids; then emit PASS format "TF_VAR_swarm_ips_id [$L] JSON string array of ${#ids[@]}"; else ids=(); emit FAIL format "TF_VAR_swarm_ips_id [$L] not a JSON array of strings"; fi
	fi
	if has "$L" TF_VAR_swarm_ips && has "$L" TF_VAR_swarm_ips_id; then
		# tests/terraform/swarm.tf: count = 3, and the inventory template reads indexes 0..2.
		if ((${#ips[@]} == 3 && ${#ids[@]} == 3)); then
			emit PASS swarm-length "[$L] 3 addresses, 3 ids"
		else
			emit FAIL swarm-length "[$L] swarm.tf needs exactly 3 of each, got ${#ips[@]} addresses and ${#ids[@]} ids"
		fi
		for ((i = 0; i < ${#ips[@]}; i++)); do is_ipv4 "${ips[i]}" || emit FAIL format "TF_VAR_swarm_ips[$i] [$L] not an IPv4 address"; done
		for ((i = 0; i < ${#ids[@]}; i++)); do is_uuid "${ids[i]}" || emit FAIL format "TF_VAR_swarm_ips_id[$i] [$L] not a UUID"; done
	fi

	if has "$L" TF_VAR_k8s_region; then
		v=$(val "$L" TF_VAR_k8s_region)
		if is_region "$v"; then emit PASS format "TF_VAR_k8s_region [$L] = $v"; else emit FAIL format "TF_VAR_k8s_region [$L] not a Scaleway region"; fi
	else
		emit INFO k8s-region "TF_VAR_k8s_region [$L] unset, the provider default region is used"
	fi

	# Two infra types sharing one address or id would fight over the same resource.
	local all=() dups
	for n in "${IPNAMES[@]}"; do has "$L" "$n" && all+=("$(val "$L" "$n")"); done
	all+=("${ips[@]}")
	dups=$(printf '%s\n' "${all[@]}" | sort | uniq -d | wc -l)
	if ((dups == 0)); then emit PASS unique "[$L] no address is used twice"; else emit FAIL unique "[$L] $dups address(es) used by more than one infra type"; fi
}

# ----------------------------------------------------------------------------------------------
# Diff (live vs next)
# ----------------------------------------------------------------------------------------------
check_diff() {
	[[ ${SYNTAX[live]} == ok && ${SYNTAX[next]} == ok ]] || { emit INFO diff "skipped, a file did not load"; return 0; }
	local n same=0 changed=0 added=0 removed=0
	for n in $(printf '%s\n' "${NAMES[live]}" "${NAMES[next]}" | tr ' ' '\n' | sort -u); do
		if has live "$n" && has next "$n"; then
			if [[ ${VAL[live:$n]} == "${VAL[next:$n]}" && ${EXP[live:$n]} == "${EXP[next:$n]}" ]]; then
				same=$((same + 1)); emit INFO diff "$n same"
			else
				changed=$((changed + 1)); emit INFO diff "$n changed"
			fi
		elif has next "$n"; then
			added=$((added + 1)); emit INFO diff "$n added"
		else
			removed=$((removed + 1)); emit INFO diff "$n removed"
		fi
	done
	emit INFO diff-summary "same=$same changed=$changed added=$added removed=$removed"
	if ((changed + added + removed == 0)); then emit PASS diff "live and next are identical"; fi
}

# ----------------------------------------------------------------------------------------------
# Functional checks
# ----------------------------------------------------------------------------------------------
need_tool() { command -v "$1" >/dev/null 2>&1 || { emit FAIL tool "$1 not found"; return 1; }; }

# scw with one file's own credentials, never the operator's profile.
scw_run() { # label outfile args...
	local L=$1 out=$2 n
	local -a e=()
	shift 2
	for n in SCW_ACCESS_KEY SCW_SECRET_KEY SCW_DEFAULT_PROJECT_ID SCW_DEFAULT_ORGANIZATION_ID; do
		has "$L" "$n" && e+=("$n=${VAL[$L:$n]}")
	done
	( cd "$T/home" && env -i PATH="$PATH" HOME="$T/home" SCW_CONFIG_PATH="$T/none.yaml" SCW_DISABLE_TELEMETRY=true \
		SCW_DISABLE_UPDATE_CHECK=true "${e[@]}" timeout 60 scw "$@" -o json >"$out" 2>"$out.err" </dev/null )
}
reason() { # errfile -> fixed words only
	if grep -qiE '(organization|project) id is required' "$1" 2>/dev/null; then printf 'default organization or project id missing'
	elif grep -qiE 'unauthor|denied|invalid.*(key|token)|forbidden|401|403|authentication' "$1" 2>/dev/null; then printf 'not authorised'
	elif grep -qiE 'not found|404' "$1" 2>/dev/null; then printf 'not found'
	else printf 'request failed'; fi
}

check_reserved_ip() { # label ctx idvalue ipvalue
	local L=$1 ctx=$2 id=$3 want=$4 zone uuid out got srv z
	if ! is_uuid "$id" || ! is_ipv4 "$want"; then emit INFO ip-lookup "$ctx [$L] skipped, bad format"; return 0; fi
	zone=$(id_zone "$L" "$id")
	uuid=$(id_uuid "$id")
	out="$T/$L-ip-$RANDOM.json"
	if ! scw_run "$L" "$out" instance ip get "$uuid" "zone=$zone"; then
		emit FAIL ip-exists "$ctx [$L] zone $zone: $(reason "$out.err")"
		return 0
	fi
	emit PASS ip-exists "$ctx [$L] zone $zone"
	z=$(jq -r '.ip.zone // empty' "$out" 2>/dev/null || true)
	[[ -z $z || $z == "$zone" ]] || emit FAIL ip-zone "$ctx [$L] expected $zone"
	got=$(jq -r '.ip.address // empty' "$out" 2>/dev/null || true)
	if [[ $got == "$want" ]]; then emit PASS ip-address "$ctx [$L] matches the reserved address"; else emit FAIL ip-address "$ctx [$L] the reserved address differs from the *_ip value"; fi
	srv=$(jq -r '.ip.server // empty | if type == "object" then .id else . end' "$out" 2>/dev/null || true)
	if [[ -n $srv ]]; then emit WARN ip-attached "$ctx [$L] attached to a server, infra may be running"; else emit PASS ip-unattached "$ctx [$L]"; fi
}

stock_word() { case $1 in available | scarce | shortage | low_stock | out_of_stock) printf '%s' "$1" ;; *) printf 'unknown' ;; esac; }

check_scaleway() {
	local L=$1 t z out i region zone
	need_tool scw || return 0
	need_tool jq || return 0
	if ! has "$L" SCW_ACCESS_KEY || ! has "$L" SCW_SECRET_KEY; then emit FAIL scaleway-auth "[$L] no SCW credentials to try"; return 0; fi
	z=$(id_zone "$L" "")
	out="$T/$L-auth.json"
	if scw_run "$L" "$out" instance ip list "zone=$z"; then
		emit PASS scaleway-auth "[$L] instance IPs readable in $z"
	else
		emit FAIL scaleway-auth "[$L] instance IP list in $z: $(reason "$out.err"); Scaleway checks skipped"
		return 0
	fi
	for t in "${TYPES[@]}"; do
		has "$L" "TF_VAR_${t}_ip_id" || continue
		check_reserved_ip "$L" "TF_VAR_${t}_ip_id" "$(val "$L" "TF_VAR_${t}_ip_id")" "$(val "$L" "TF_VAR_${t}_ip")"
	done
	local ips=() ids=()
	if swarm_list "$L" TF_VAR_swarm_ips ips && swarm_list "$L" TF_VAR_swarm_ips_id ids; then
		for ((i = 0; i < ${#ids[@]} && i < ${#ips[@]}; i++)); do
			check_reserved_ip "$L" "TF_VAR_swarm_ips_id[$i]" "${ids[i]}" "${ips[i]}"
		done
	fi

	# k8s: a Load Balancer IP in "<region>-1", unattached.
	region=$(k8s_region "$L")
	if ! is_region "$region"; then emit FAIL k8s-zone "[$L] region is not a Scaleway region"; return 0; fi
	zone="$region-1"
	emit INFO k8s-zone "[$L] $zone"
	out="$T/$L-lbip.json"
	if ! scw_run "$L" "$out" lb ip list "zone=$zone"; then
		emit FAIL scaleway-auth "[$L] LB IP list in $zone: $(reason "$out.err")"
	else
		emit PASS scaleway-auth "[$L] LB IPs readable in $zone"
		local want m lbid
		want=$(val "$L" TF_VAR_k8s_ip)
		if is_ipv4 "$want"; then
			m=$(jq -c --arg a "$want" '[.[] | select(.ip_address == $a)] | first // empty' "$out" 2>/dev/null || true)
			if [[ -z $m ]]; then
				emit FAIL lb-ip "TF_VAR_k8s_ip [$L] no LB IP with that address in $zone"
			else
				emit PASS lb-ip "TF_VAR_k8s_ip [$L] found in $zone"
				if [[ $(jq -r '.ip_address | contains(":")' <<<"$m") == false ]]; then emit PASS lb-ip-family "TF_VAR_k8s_ip [$L] IPv4"; else emit FAIL lb-ip-family "TF_VAR_k8s_ip [$L] not IPv4"; fi
				lbid=$(jq -r '.lb_id // empty' <<<"$m")
				if [[ -z $lbid ]]; then emit PASS lb-ip-unattached "TF_VAR_k8s_ip [$L]"; else emit FAIL lb-ip-unattached "TF_VAR_k8s_ip [$L] attached to a load balancer"; fi
			fi
		else
			emit INFO lb-ip "TF_VAR_k8s_ip [$L] skipped, bad format"
		fi
	fi

	# Stock moves, so it informs and never fails.
	local s
	out="$T/$L-stock-k8s.json"
	if scw_run "$L" "$out" k8s cluster-type list "region=$region"; then
		s=$(stock_word "$(jq -r '[.[] | select(.name == "kapsule")][0].availability // empty' "$out" 2>/dev/null || true)")
		if [[ $s == available ]]; then emit INFO stock "kapsule $region available"; else emit WARN stock "kapsule $region $s"; fi
	else
		emit WARN stock "kapsule $region unreadable"
	fi
	out="$T/$L-stock-pop2.json"
	if scw_run "$L" "$out" instance server-type list "zone=$zone"; then
		s=$(stock_word "$(jq -r '[.[] | select(.name == "POP2-2C-8G")][0].availability // empty' "$out" 2>/dev/null || true)")
		if [[ $s == available ]]; then emit INFO stock "POP2-2C-8G $zone available"; else emit WARN stock "POP2-2C-8G $zone $s"; fi
	else
		emit WARN stock "POP2-2C-8G $zone unreadable"
	fi
	out="$T/$L-stock-lb.json"
	if scw_run "$L" "$out" lb lb-types list "zone=$zone"; then
		s=$(stock_word "$(jq -r '[.[] | select(.name == "lb-s")][0].stock_status // empty' "$out" 2>/dev/null || true)")
		if [[ $s == available ]]; then emit INFO stock "lb-s $zone available"; else emit WARN stock "lb-s $zone $s"; fi
	else
		emit WARN stock "lb-s $zone unreadable"
	fi
}

# ---- DNS ----
declare -A DNS_PUB DNS_AUTH DNS_AUTH_N
dig_a() { # name server -> IPv4 lines
	timeout 20 dig +short +time=3 +tries=2 A "$1" "@$2" 2>/dev/null | grep -E "^($OCT\.){3}$OCT\$" | sort -u | tr '\n' ' ' || true
}
zone_ns() { # domain -> up to 4 name server hosts
	local d=$1 ns
	while [[ $d == *.* ]]; do
		ns=$(timeout 20 dig +short +time=3 +tries=2 NS "$d" @1.1.1.1 2>/dev/null | sed 's/\.$//' | grep -E '^[A-Za-z0-9][A-Za-z0-9.-]*$' | head -4 || true)
		if [[ -n $ns ]]; then printf '%s\n' "$ns"; return 0; fi
		d=${d#*.}
	done
}
resolve_domains() {
	local key dom probe pub auth ns s nsn reach
	for key in "${DOM_KEYS[@]}"; do
		dom=${DOM_VAL[$key]}
		probe="bwsc$RANDOM$RANDOM.$dom"
		pub=$(dig_a "$probe" 1.1.1.1)
		[[ -n $pub ]] || pub=$(dig_a "$dom" 1.1.1.1)
		DNS_PUB[$key]=$pub
		auth="" nsn=0 reach=0
		while IFS= read -r ns; do
			[[ -n $ns ]] || continue
			nsn=$((nsn + 1))
			s=$(dig_a "$probe" "$ns")
			[[ -n $s ]] || s=$(dig_a "$dom" "$ns")
			if [[ -n $s ]]; then reach=$((reach + 1)); auth+="$s|"; fi
		done < <(zone_ns "$dom")
		DNS_AUTH[$key]=$auth
		DNS_AUTH_N[$key]="$nsn $reach"
	done
}

dns_mapped() { # file -> var name or empty
	case $1 in
	*_DOCKER) printf 'TF_VAR_docker_ip' ;;
	*_AUTOCONF) printf 'TF_VAR_autoconf_ip' ;;
	*_KUBERNETES) printf 'TF_VAR_k8s_ip' ;;
	*_LINUX) printf 'TF_VAR_linux_ip' ;;
	esac
}

in_words() { [[ " $2" == *" $1 "* ]]; }

# With --next, the candidate gates the DNS mapping: the live file only warns, since the records
# move between the two uploads (BW-355 cutover).
check_dns() {
	local L=$1 key file name map want infra=" " n set bad auth_ok reach nsn part soft=0
	local -a ips=() parts=()
	[[ $L == live && -n $NEXT ]] && soft=1
	for n in "${IPNAMES[@]}"; do has "$L" "$n" && infra+="$(val "$L" "$n") "; done
	swarm_list "$L" TF_VAR_swarm_ips ips && infra+="${ips[*]} "
	for key in "${DOM_KEYS[@]}"; do
		file=${key%%/*}
		name=${key#*/}
		map=$(dns_mapped "$file")
		want=""
		[[ -z $map ]] || want=$(val "$L" "$map")
		# public resolver view
		set=${DNS_PUB[$key]}
		dns_verdict "$L" dns-public "$file/$name" "$map" "$want" "$infra" "$set" "$soft"
		# authoritative view
		read -r nsn reach <<<"${DNS_AUTH_N[$key]}"
		if ((nsn == 0)); then emit WARN dns-auth "$file/$name [$L] no authoritative name server found"; continue; fi
		if ((reach == 0)); then emit FAIL dns-auth "$file/$name [$L] none of $nsn authoritative servers returned an A record"; continue; fi
		bad=0 auth_ok=""
		IFS='|' read -r -a parts <<<"${DNS_AUTH[$key]}"
		for part in "${parts[@]}"; do
			[[ -n $part ]] || continue
			auth_ok+="$part "
			if [[ -n $want ]] && ! in_words "$want" "$part "; then bad=$((bad + 1)); fi
		done
		if [[ -n $want && $bad -gt 0 && $bad -lt ${#parts[@]} ]]; then
			dns_mismatch "$L" dns-auth "$file/$name" "$bad of $reach authoritative servers disagree with $map" "$soft"
		else
			dns_verdict "$L" dns-auth "$file/$name" "$map" "$want" "$infra" "$auth_ok" "$soft"
		fi
	done
}

declare -A DNS_SOFT_SEEN
dns_mismatch() { # label check ctx why soft: FAIL, or one WARN per domain when soft
	local L=$1 chk=$2 ctx=$3 why=$4 soft=$5
	if ((soft)); then
		[[ -z ${DNS_SOFT_SEEN[$ctx]+x} ]] || return 0
		DNS_SOFT_SEEN[$ctx]=1
		emit WARN dns-mapping "$ctx [$L] does not match live (expected during a cutover)"
	else
		emit FAIL "$chk" "$ctx [$L] $why"
	fi
}

dns_verdict() { # label check ctx map want infra set soft
	local L=$1 chk=$2 ctx=$3 map=$4 want=$5 infra=$6 set=$7 soft=$8 ip hit=0 w=()
	read -r -a w <<<"$set"
	for ip in "${w[@]}"; do in_words "$ip" "$infra" && hit=1; done
	if ((${#w[@]} == 0)); then emit FAIL "$chk" "$ctx [$L] no A record"; return 0; fi
	if ((hit == 0)); then dns_mismatch "$L" "$chk" "$ctx" "resolves to none of the infra IPs in the file" "$soft"; return 0; fi
	if [[ -z $map ]]; then emit INFO "$chk" "$ctx [$L] resolves to an infra IP, no type mapping for this secret"; return 0; fi
	if [[ -n $want ]] && in_words "$want" "$set "; then
		emit PASS "$chk" "$ctx [$L] -> $map"
	else
		dns_mismatch "$L" "$chk" "$ctx" "does not resolve to $map" "$soft"
	fi
}

# ---- GitHub token ----
gh_get() { # label path outprefix -> prints status code
	local L=$1 path=$2 pre=$3 hf code
	hf="$T/$L-gh-hdr"
	umask 077
	printf 'Authorization: Bearer %s\nAccept: application/vnd.github+json\nX-GitHub-Api-Version: 2022-11-28\nUser-Agent: secrets-check\n' "$(val "$L" GITHUB_TOKEN)" >"$hf"
	code=$(timeout 40 curl -sS --max-time 30 -o "$pre.body" -D "$pre.hdr" -H "@$hf" -w '%{http_code}' "https://api.github.com$path" 2>/dev/null || true)
	# Only a three digit status ever leaves this function.
	[[ $code =~ ^[0-9]{3}$ ]] || code=000
	printf '%s' "$code"
}
check_github() {
	local L=$1 code login acct exp days epoch pre scopes
	pre="$T/$L-gh"
	need_tool curl || return 0
	need_tool jq || return 0
	has "$L" GITHUB_TOKEN || return 0
	code=$(gh_get "$L" /user "$pre-user")
	if [[ $code != 200 ]]; then emit FAIL github-token "[$L] GET /user returned HTTP $code"; return 0; fi
	login=$(jq -r '.login // empty' "$pre-user.body" 2>/dev/null || true)
	acct=$(val "$L" GITHUB_ACCOUNT)
	if [[ -n $login && ${login,,} == "${acct,,}" ]]; then emit PASS github-token "[$L] authenticates as GITHUB_ACCOUNT"; else emit FAIL github-token "[$L] token owner differs from GITHUB_ACCOUNT"; fi
	exp=$(grep -i '^github-authentication-token-expiration:' "$pre-user.hdr" 2>/dev/null | head -1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//' || true)
	if [[ $exp =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
		epoch=$(date -u -d "${exp:0:10}" +%s 2>/dev/null || echo 0)
		days=$(((epoch - $(date -u +%s)) / 86400))
		if ((days < 0)); then emit FAIL github-expiry "[$L] expired on ${exp:0:10}"
		elif ((days < 30)); then emit WARN github-expiry "[$L] expires ${exp:0:10} ($days days)"
		else emit PASS github-expiry "[$L] expires ${exp:0:10} ($days days)"; fi
	else
		emit INFO github-expiry "[$L] no expiration header"
	fi
	scopes=$(grep -i '^x-oauth-scopes:' "$pre-user.hdr" 2>/dev/null | head -1 | cut -d: -f2- | tr -d '\r ' || true)
	if [[ -n ${scopes:-} ]]; then
		if [[ $scopes =~ ^[a-z:_,-]+$ ]]; then emit INFO github-scopes "[$L] $scopes"; else emit INFO github-scopes "[$L] present"; fi
		in_words repo "${scopes//,/ } " || emit WARN github-scopes "[$L] no repo scope, the runner role needs repo admin"
	else
		emit INFO github-scopes "[$L] no X-OAuth-Scopes header (fine-grained or app token)"
	fi
	# monolithprojects.github_actions_runner 1.18.7 POSTs /repos/<owner>/<repo>/actions/runners/registration-token
	# and GETs /repos/<owner>/<repo>/actions/runners. Both need repo admin; the POST is not exercised here.
	code=$(gh_get "$L" /repos/bunkerity/bunkerweb "$pre-repo")
	if [[ $code == 200 ]]; then
		if [[ $(jq -r '.permissions.admin // false' "$pre-repo.body" 2>/dev/null) == true ]]; then
			emit PASS github-runner "[$L] admin on bunkerity/bunkerweb"
		else
			emit FAIL github-runner "[$L] no admin on bunkerity/bunkerweb, registration-token would be refused"
		fi
	else
		emit FAIL github-runner "[$L] GET repo returned HTTP $code"
	fi
	code=$(gh_get "$L" /repos/bunkerity/bunkerweb/actions/runners "$pre-runners")
	if [[ $code == 200 ]]; then emit PASS github-runner "[$L] can list repo runners"; else emit FAIL github-runner "[$L] GET actions/runners returned HTTP $code"; fi
	emit INFO github-runner "[$L] registration-token POST not exercised (read-only)"
}

# ----------------------------------------------------------------------------------------------
# Terraform plans
# ----------------------------------------------------------------------------------------------
TF_READY=0
declare -A TF_INIT
TF_DIR=""
# shellcheck disable=SC2016
RUNNER='. "$1" >/dev/null 2>&1 </dev/null; shift; exec "$@"'
tf_prepare() {
	need_tool terraform || return 0
	need_tool ssh-keygen || return 0
	[[ -f $REPO/tests/terraform/providers.tf ]] || { emit FAIL tool "tests/terraform not found next to the script"; return 0; }
	mkdir -p "$T/tfcache" "$T/tfhome/.ssh"
	# file("~/.ssh/id_rsa.pub") is read at plan time: a throwaway key in a temp HOME.
	ssh-keygen -q -t rsa -b 2048 -N '' -f "$T/tfhome/.ssh/id_rsa" >/dev/null 2>&1
	TF_READY=1
}

# One `terraform init` per type, shared by every file: the provider set differs per type
# (hashicorp/local only shows up through the resources), so the lock file is per type too.
tf_init() { # type -> sets TF_DIR to the initialised directory, returns 1 on failure
	local t=$1 d="$T/tf-init-$1"
	TF_DIR=$d
	if [[ -n ${TF_INIT[$t]-} ]]; then
		[[ ${TF_INIT[$t]} == ok ]]
		return
	fi
	mkdir -p "$d"
	cp "$REPO/tests/terraform/providers.tf" "$REPO/tests/terraform/$t.tf" "$d/"
	cp -r "$REPO/tests/terraform/templates" "$d/"
	if (cd "$d" && env -i PATH="$PATH" HOME="$T/tfhome" CHECKPOINT_DISABLE=1 TF_IN_AUTOMATION=1 TF_PLUGIN_CACHE_DIR="$T/tfcache" \
		timeout 600 terraform init -input=false -no-color >"$d/init.log" 2>&1); then
		TF_INIT[$t]=ok
		emit PASS terraform-init "$t"
	else
		TF_INIT[$t]=bad
		emit FAIL terraform-init "$t ($(tf_category "$d/init.log"))"
		return 1
	fi
}

tf_plan() { # label type
	local L=$1 t=$2 d="$T/tf-$1-$2" rc=0 line n file
	file=${FILE[$L]}
	tf_init "$t" || return 0
	cp -a "$TF_DIR" "$d"
	# Source like tests/create.sh does (no set -a), so an unexported variable never reaches terraform.
	(cd "$d" && env -i PATH="$PATH" HOME="$T/tfhome" CHECKPOINT_DISABLE=1 TF_IN_AUTOMATION=1 TF_PLUGIN_CACHE_DIR="$T/tfcache" \
		bash -c "$RUNNER" _ "$file" \
		timeout 300 terraform plan -refresh=false -lock=false -input=false -no-color >"$d/plan.log" 2>&1) || rc=$?
	if ((rc == 0)); then
		line=$(grep -E '^Plan: [0-9]+ to add' "$d/plan.log" | head -1 || true)
		if [[ $line =~ ^Plan:\ ([0-9]+)\ to\ add ]]; then n=${BASH_REMATCH[1]}; emit PASS terraform-plan "$t [$L] Plan: $n to add"; else emit WARN terraform-plan "$t [$L] plan succeeded without a Plan line"; fi
	else
		emit FAIL terraform-plan "$t [$L] exit $rc ($(tf_category "$d/plan.log"))"
	fi
}

# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------
LABELS=(live)
declare -A FILE=([live]=$LIVE [next]=$NEXT)
[[ -z $NEXT ]] || LABELS+=(next)

need_tool jq || { printf 'INFO summary pass=%s warn=%s fail=%s\n' "$CNT_PASS" "$CNT_WARN" "$CNT_FAIL"; exit 1; }

# Phase 0: load and mask, before anything else is printed.
for L in "${LABELS[@]}"; do load_env "$L" "${FILE[$L]}"; done
load_domains
mask_all

for L in "${LABELS[@]}"; do check_structure "$L"; done
[[ -z $NEXT ]] || check_diff
check_domains

if ((NO_REMOTE)); then
	emit INFO remote "skipped (--no-remote): scaleway, dns, github and terraform"
else
	for L in "${LABELS[@]}"; do if [[ ${SYNTAX[$L]} == ok ]]; then check_scaleway "$L"; fi; done
	if [[ -n $DOMAINS_DIR ]]; then
		for f in "${DOM_FILES[@]}"; do
			[[ -n $(dns_mapped "$f") ]] || emit INFO dns-mapping "$f no type mapping in the workflows"
		done
		emit INFO dns-mapping "swarm: no TEST_DOMAINS secret in the workflows"
		if need_tool dig; then
			resolve_domains
			for L in "${LABELS[@]}"; do if [[ ${SYNTAX[$L]} == ok ]]; then check_dns "$L"; fi; done
		fi
	else
		emit INFO dns "skipped, no --domains-dir"
	fi
	for L in "${LABELS[@]}"; do if [[ ${SYNTAX[$L]} == ok ]]; then check_github "$L"; fi; done
	if ((NO_TF)); then
		emit INFO terraform "skipped (--no-terraform)"
	else
		tf_prepare
		if ((TF_READY)); then
			for L in "${LABELS[@]}"; do
				[[ ${SYNTAX[$L]} == ok ]] || continue
				for t in docker autoconf linux swarm k8s; do tf_plan "$L" "$t"; done
			done
		fi
	fi
fi

printf 'INFO summary pass=%s warn=%s fail=%s\n' "$CNT_PASS" "$CNT_WARN" "$CNT_FAIL"
if ((CNT_FAIL > 0)); then exit 1; fi
