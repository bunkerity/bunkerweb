# `bw_db_migrate.py` (BunkerWeb DB backend migration)

`bw_db_migrate.py` migrates BunkerWeb database data between supported backends by:
1. Creating the BunkerWeb schema on the target backend (Alembic).
2. Dumping all BunkerWeb tables from the source backend into intermediate JSONL files.
3. Importing those JSONL files into the target backend.
4. Verifying per-table row counts between source and target.

It can also run in a “no changes” mode (`--dry-run` / `--test-target`) or launch an interactive TUI (`--tui`).

## When to use it

Use this script when you want to move your BunkerWeb runtime database backend, for example:

- MySQL/MariaDB -> PostgreSQL
- PostgreSQL -> MySQL/MariaDB
- Any supported backend -> SQLite (or vice-versa)

## Requirements

- Python dependencies as shipped with the BunkerWeb installation.
- Network connectivity (when using remote source/target backends).
- Sufficient privileges on the source/target to read tables and write/import the BunkerWeb schema.

## Configuration inputs

The script reads connection URIs from an environment file, or from CLI arguments.

### Environment file

By default, use:

`/etc/bunkerweb/variables.env`

It should contain at least:

- `DATABASE_URI`: source database SQLAlchemy URI
- `DB_MIGRATION_TARGET_URI`: target database SQLAlchemy URI

### CLI overrides

You can override either value with:

- `--source-uri <URI>`
- `--target-uri <URI>`

## CLI options

Run:

`python3 bw_db_migrate.py [options]`

Common options:

- `--env-file <path>`
  - Environment file path (default: `/etc/bunkerweb/variables.env`)
- `--source-uri <URI>`
  - Source SQLAlchemy URI override
- `--target-uri <URI>`
  - Target SQLAlchemy URI override
- `--test-target`
  - Only tests that the target is reachable and appears empty (no migrations/copy)
- `--dry-run`
  - Summarizes what would be migrated by counting rows per BunkerWeb table
  - Does not modify the target
- `--tui`
  - Launches the interactive terminal UI to collect inputs
- `--auto-switch`
  - After a successful migration:
    1. Updates `DATABASE_URI` in the `--env-file` to point to the migrated target.
    2. Restarts BunkerWeb services via a best-effort init-system restart:
       - systemd if available (restarts `bunkerweb`, `bunkerweb-scheduler`, `bunkerweb-ui`)
       - otherwise falls back to init scripts / `service`

## Examples

### 1) Quick connectivity + empty target check

`python3 bw_db_migrate.py --test-target`

### 2) Dry-run (counts rows)

`python3 bw_db_migrate.py --dry-run`

Note: dry-run runs a `COUNT` query per known BunkerWeb table, so it can be slow on large datasets.

### 3) Full migration

`python3 bw_db_migrate.py`

### 4) Full migration with auto-switch

`python3 bw_db_migrate.py --auto-switch`

### 5) Interactive TUI

`python3 bw_db_migrate.py --tui`

## SQLite target notes (important)

If the target backend is SQLite (e.g. `sqlite:////var/lib/bunkerweb/db.sqlite3`):

- The target file must be empty (the script checks that BunkerWeb tables contain 0 rows).
- If the file already exists and has data, the script will instruct you to move/rename it.
  - Example:
    - `mv /var/lib/bunkerweb/db.sqlite3 /var/lib/bunkerweb/db.sqlite3.bak-<timestamp>`
- After a successful migration, the script attempts to `chown` the SQLite DB file to match the parent directory owner/group.
  - This helps avoid scheduler failures caused by SQLite journal/WAL permission issues.

## Troubleshooting

- Target not empty:
  - For SQL backends: recreate the target database.
  - For SQLite: move/rename the DB file, then re-run.
- Unencrypted connection warnings:
  - When SSL is not enabled in the target URI, the script emits warnings and performs best-effort connectivity checks.
- Scheduler retry loops after auto-switch:
  - If using SQLite, ensure the SQLite file is writable by the runtime service user (commonly `nginx`).

