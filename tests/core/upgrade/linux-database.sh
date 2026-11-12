#!/bin/bash
# Database checks around a Linux package upgrade (tests/core/upgrade.yml, Linux arm). The runner calls it
# twice per upgrade path, against the SQLite database of the `bunkerweb-linux` systemd container:
#
#   snapshot <name>   on the old release, before the upgrade. Record whether the rc3 table already
#                     exists (recent prereleases have it), and write a marker table into the database.
#   verify <name>     on the package built from this checkout, after the upgrade. The version recorded in
#                     the database moved, the migration ran (alembic_version exists, it is only created by
#                     the scheduler's upgrade path), the rc3 table exists, the marker survived (the database
#                     was migrated, not replaced by a new one) and the service the old release served is
#                     still declared. Report whether the upgrade created the rc3 table or kept it.
#
# Why a marker: a database created from scratch by the new code also has the rc3 table, so the table
# alone cannot tell an upgrade that migrated the old database from one that threw it away.

set -Eeuo pipefail

mode="${1:-}"
name="${2:-}"
if [ -z "$name" ] || { [ "$mode" != "snapshot" ] && [ "$mode" != "verify" ]; }; then
	echo "usage: $0 snapshot|verify <name>" >&2
	exit 2
fi

container="bunkerweb-linux"
database="/var/lib/bunkerweb/db.sqlite3"
state_dir="${TMPDIR:-/tmp}/linux-upgrade"
version_file="${state_dir}/${name}.version"
login_failures_file="${state_dir}/${name}.login-failures"
login_failures_table="bw_ui_login_failures"
service_name="www.example.com"

# Read-only unless the caller says otherwise: a missing file must never be created by root, the
# scheduler (nginx) could not write it afterwards.
query() {
	docker exec -u 0 "$container" sqlite3 -readonly "$database" "$1"
}

fail() {
	echo "linux-database ${mode} ${name}: $1" >&2
	exit 1
}

table_count() {
	query "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = '$1'"
}

version="$(query "SELECT version FROM bw_metadata WHERE id = 1")" || fail "cannot read the database version"
[ -n "$version" ] || fail "the database version is empty"

if [ "$mode" = "snapshot" ]; then
	login_failures_before="$(table_count "$login_failures_table")" || fail "cannot read whether ${login_failures_table} exists"

	mkdir -p "$state_dir"
	echo "$version" >"$version_file"
	echo "$login_failures_before" >"$login_failures_file"

	# The checkpoint folds the marker into the main file: the package backs that file up on upgrade.
	docker exec -u 0 "$container" sqlite3 "$database" \
		".timeout 10000" \
		"CREATE TABLE IF NOT EXISTS upgrade_marker (name TEXT PRIMARY KEY)" \
		"INSERT OR REPLACE INTO upgrade_marker VALUES ('${name}')" \
		"PRAGMA wal_checkpoint(TRUNCATE)" >/dev/null || fail "cannot write the marker"
	[ "$(query "SELECT count(*) FROM upgrade_marker WHERE name = '${name}'")" = "1" ] || fail "the marker was not written"

	echo "linux-database snapshot ${name}: database version ${version}"
	echo "linux-database snapshot ${name}: all checks passed"
	exit 0
fi

[ -s "$version_file" ] || fail "no snapshot of the old release (${version_file})"
[ -s "$login_failures_file" ] || fail "no snapshot of ${login_failures_table} (${login_failures_file})"
old_version="$(cat "$version_file")"
[ "$version" != "$old_version" ] || fail "the database version is still ${old_version}: the database was not migrated"
[ "$(table_count alembic_version)" = "1" ] || fail "alembic_version is missing: the scheduler's migration did not run"
# The table alone is no proof: a database that init_tables created from scratch has it too. The revision
# has to be the head of the migrations of THIS checkout (the one no other migration revises), read here and not
# from the installed package: a package that dropped a migration would agree with itself.
versions_dir="${UPGRADE_VERSIONS_DIR:-src/common/db/alembic/sqlite_versions}"
head="$(python3 - "$versions_dir" <<'PY'
import re
import sys
from pathlib import Path

files = sorted(Path(sys.argv[1]).glob("*.py"))
revisions = {re.search(r'^revision: str = "(\w+)"', f.read_text(), re.M).group(1) for f in files}
revised = {m for f in files for m in re.findall(r'^down_revision: .*?"(\w+)"', f.read_text(), re.M)}
print("\n".join(sorted(revisions - revised)))
PY
)"
[ -n "$head" ] && [ "$(echo "$head" | wc -l)" = "1" ] || fail "cannot tell the migration head of ${versions_dir} (got: ${head:-nothing})"
current="$(query "SELECT version_num FROM alembic_version")"
[ "$current" = "$head" ] || fail "the database is at revision ${current}, the migration head of this checkout is ${head}"
[ "$(table_count "$login_failures_table")" = "1" ] || fail "${login_failures_table} is missing after the upgrade"
[ "$(query "SELECT count(*) FROM upgrade_marker WHERE name = '${name}'" 2>/dev/null || true)" = "1" ] || fail "the marker written before the upgrade is gone: the database was replaced, not migrated"
[ "$(query "SELECT count(*) FROM bw_services WHERE id = '${service_name}'")" -ge 1 ] || fail "${service_name} is not declared after the upgrade"

echo "linux-database verify ${name}: database version ${old_version} -> ${version}, revision ${current} (head)"
if [ "$(cat "$login_failures_file")" = "0" ]; then
	echo "linux-database verify ${name}: migration created ${login_failures_table}"
else
	echo "linux-database verify ${name}: ${login_failures_table} already existed before the upgrade"
fi
echo "linux-database verify ${name}: all checks passed"
