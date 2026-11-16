#!/bin/bash
# Apply BunkerWeb patches to one vendored file, from deps.json "post_install" steps (run from the repo root).
#   apply_patch.sh <file> <patch>...      (several patches are applied in the order given)
# - the patches apply cleanly          -> applied
# - the patches are already applied    -> accepted, only after the whole chain reverses cleanly (last patch first)
# - anything else (conflict)           -> exit 1, file untouched, no .orig or .rej left behind
# Every attempt runs on a staged copy, so a patch with several hunks (or a chain of patches on one file) never half-applies.
set -u

if [ "$#" -lt 2 ]; then
	echo "usage: $0 <file> <patch>..." >&2
	exit 2
fi
file="$1"
shift
patches=("$@")

stage="$(mktemp -d)" || exit 1
trap 'rm -rf "$stage"' EXIT

# --no-backup-if-mismatch: no .orig after a fuzzy hunk; -r -: rejected hunks are discarded, never written to a .rej
try_chain() { # $1 = forward|reverse ; leaves the result in $stage/f
	local dir="$1" p i
	cp -p -- "$file" "$stage/f" || return 1
	if [ "$dir" = forward ]; then
		for p in "${patches[@]}"; do
			patch --forward --batch --no-backup-if-mismatch -r - "$stage/f" "$p" >/dev/null 2>&1 || return 1
		done
	else
		for ((i = ${#patches[@]} - 1; i >= 0; i--)); do
			patch --reverse --batch --no-backup-if-mismatch -r - "$stage/f" "${patches[i]}" >/dev/null 2>&1 || return 1
		done
	fi
}

if try_chain forward; then
	cat -- "$stage/f" >"$file" || exit 1 # cat > keeps the target's mode and inode
	echo "patched $file (${#patches[@]} patch(es))"
elif try_chain reverse; then
	echo "ℹ️ already applied to $file (${#patches[@]} patch(es))"
else
	echo "❌ ${patches[*]} neither apply to nor are already applied to $file" >&2
	exit 1
fi
