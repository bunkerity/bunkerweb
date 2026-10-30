#!/usr/bin/env python3

from contextlib import closing
from datetime import datetime, timedelta
from hashlib import sha256
import re
from json import dumps, loads
from os import getenv
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, run
from shutil import disk_usage, which
from sqlite3 import connect as sqlite_connect
from sys import exit as sys_exit, path as sys_path
from tempfile import TemporaryDirectory
from typing import List, Literal, Optional, Tuple
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile
from zlib import error as zlib_error

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from sqlalchemy import inspect, text
from sqlalchemy.engine.url import make_url

from common_utils import acquire_db_lock as _acquire_db_lock, bytes_hash, DatabaseLockBusy, release_db_lock, safe_zip_extractall  # type: ignore  # noqa: F401
from Database import Database  # type: ignore
from logger import getLogger  # type: ignore
from model import Base  # type: ignore

LOGGER = getLogger("BACKUP")

BACKUP_DIR = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
# Write probes (Database.py) create and drop test_<uuid4 hex>; they are not user data and can vanish or linger mid-dump
TEST_TABLE_PATTERN = re.compile(r"test_[0-9a-f]{32}")
# The same shape as a psql pattern, so a user table with a 32-character name after "test_" is still dumped
POSTGRESQL_TEST_TABLE_PATTERN = "test_" + "[0-9a-f]" * 32
DUMP_ATTEMPTS = 5
DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")


def mysql_client_command(operation: Literal["dump", "restore"]) -> tuple[str, bool]:
    mariadb_command = "mariadb-dump" if operation == "dump" else "mariadb"
    if which(mariadb_command):
        return mariadb_command, True
    return ("mysqldump" if operation == "dump" else "mysql"), False


def mysql_connection_args(query_args, mariadb_client: bool) -> list[str]:
    args = []
    ssl = query_args.get("ssl")
    if isinstance(ssl, tuple):
        ssl = ssl[-1]
    ssl = str(ssl).lower() if ssl is not None else None

    if ssl == "true":
        args.append("--ssl")
    elif ssl == "false":
        args.append("--skip-ssl")
    elif mariadb_client:
        # MariaDB clients verify opportunistic TLS by default. MySQL's generated
        # certificate is self-signed, so keep encryption but skip verification
        # unless DATABASE_URI explicitly requests SSL.
        args.append("--skip-ssl-verify-server-cert")

    charset = query_args.get("charset")
    if isinstance(charset, tuple):
        charset = charset[-1]
    if charset:
        args.extend(["--default-character-set", str(charset)])
    return args


def acquire_db_lock(timeout: float = 30.0) -> int:
    """Acquire the database lock (fcntl.flock, real mutual exclusion) to prevent concurrent
    access to the database. Returns a handle to pass to release_db_lock(). Raises
    DatabaseLockBusy if the lock is still held by another process after `timeout` seconds.
    """
    return _acquire_db_lock(DB_LOCK_FILE, timeout=timeout)


def check_disk_space(database: str, db: Database, backup_dir: Path, db_path: Optional[Path] = None) -> bool:
    """Check whether backup_dir has enough free space to hold a new backup.

    The estimated dump size uses a 2× multiplier over the raw database size to
    account for SQL text being larger than the on-disk binary representation
    (especially for SQLite). After zip compression the actual backup file will
    be significantly smaller, so this is intentionally conservative.

    Returns True when there is enough space or when the check cannot be
    performed (so the backup is never silently skipped due to a query error).
    """
    try:
        if database == "sqlite":
            if db_path is None or not db_path.exists():
                LOGGER.warning("Cannot check disk space: SQLite database path is not available.")
                return True
            db_size = db_path.stat().st_size
        elif database in ("mariadb", "mysql"):
            with db.sql_engine.connect() as conn:
                row = conn.execute(text("SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = DATABASE()")).fetchone()
            db_size = int(row[0]) if row and row[0] else 0
        elif database == "postgresql":
            with db.sql_engine.connect() as conn:
                row = conn.execute(text("SELECT pg_database_size(current_database())")).fetchone()
            db_size = int(row[0]) if row and row[0] else 0
        else:
            return True  # unsupported engine, skip check

        # SQL text dumps are typically 2–3× the raw binary DB size. Use 2× as a
        # conservative lower bound for the uncompressed dump that will be held
        # in memory (proc.stdout) before compression.
        estimated_size = db_size * 2
        free = disk_usage(backup_dir).free

        LOGGER.debug(f"Disk space check: DB ~{db_size:,} B, estimated dump ~{estimated_size:,} B, free in {backup_dir} ~{free:,} B")

        if free < estimated_size:
            LOGGER.error(
                f"Not enough disk space for backup: need ~{estimated_size:,} bytes "
                f"(2× DB size of {db_size:,} B), but only {free:,} bytes free in {backup_dir}"
            )
            return False

        return True
    except Exception as exc:
        # Common expected causes: DB user lacks SELECT on information_schema /
        # pg_database, or the connection is temporarily unavailable.
        # In all cases we skip the check and let the backup proceed — a failed
        # space check must never prevent a backup from running.
        exc_str = str(exc).lower()
        if any(kw in exc_str for kw in ("access denied", "permission denied", "insufficient privilege", "connection", "refused", "timeout")):
            LOGGER.debug(f"Disk space check skipped (DB user may lack access to system tables): {exc}")
        else:
            LOGGER.warning(f"Disk space check skipped (unexpected error): {exc}")
        return True


# Towers of Hanoi retention: (number of buckets, bucket width), applied to consecutive age ranges.
# Backups younger than 6h keep one per hour, the next 4h one per 2h, and so on up to 2050h (~85 days).
HANOI_TIERS: List[Tuple[int, timedelta]] = [
    (6, timedelta(hours=1)),  # ages 0-6h
    (2, timedelta(hours=2)),  # 6-10h
    (2, timedelta(hours=4)),  # 10-18h
    (2, timedelta(hours=8)),  # 18-34h
    (2, timedelta(hours=16)),  # 34-66h
    (2, timedelta(hours=32)),  # 66-130h
    (2, timedelta(hours=64)),  # 130-258h
    (2, timedelta(hours=128)),  # 258-514h
    (2, timedelta(hours=256)),  # 514-1026h
    (2, timedelta(hours=512)),  # 1026-2050h (~85 days)
]


def hanoi_rotation(backup_files: List[Path], now: datetime) -> List[Path]:
    """Return the list of files to DELETE under Towers-of-Hanoi rotation.

    Each tier covers a fixed age range and keeps the newest backup of every bucket of its width.
    Buckets are aligned on the epoch, not on *now*, and every width is twice the previous one, so a
    coarser bucket is exactly two finer ones: the backup it keeps is always one the finer tier kept,
    and a backup is only deleted once a newer one covers the same bucket. Sliding windows anchored on
    *now* broke that and deleted backups a later window needed.

    Keeps 24 to 34 files (a tier's age range can touch one bucket more than its count); the oldest is
    64 to 85 days old, depending on where the buckets fall.
    Backups dated in the future (clock change) are kept.
    """
    timed: List[Tuple[datetime, Path]] = []
    for f in backup_files:
        m = re.search(r"backup-\w+-(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", f.name)
        if m:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S").astimezone()
            timed.append((dt, f))

    timed.sort(reverse=True)  # newest first

    keep = {f for dt, f in timed if dt > now}
    tier_start = timedelta(0)
    for count, interval in HANOI_TIERS:
        tier_end = tier_start + count * interval
        newest = {}
        for dt, f in timed:
            if tier_start <= now - dt < tier_end:
                newest.setdefault(int(dt.timestamp() // interval.total_seconds()), f)
        keep.update(newest.values())
        tier_start = tier_end

    return [f for _, f in timed if f not in keep]


def update_cache_file(db: Database, backup_dir: Path) -> str:
    """Update the cache file in the database."""
    backup_data = loads(db.get_job_cache_file("backup-data", "backup.json") or "{}")
    backup_data["files"] = sorted([file.name for file in backup_dir.glob("backup-*.zip")])
    backup_data["date"] = datetime.now().astimezone().isoformat()
    content = dumps(backup_data, indent=2).encode()
    checksum = bytes_hash(content)
    err = db.upsert_job_cache(None, "backup.json", content, job_name="backup-data", checksum=checksum)
    if err:
        LOGGER.error(f"Failed to update the backup.json cache file: {err}")
        return err

    LOGGER.info("Backup cache file updated successfully")
    return ""


def backup_database(current_time: datetime, db: Database = None, backup_dir: Path = BACKUP_DIR):
    """Backup the database."""
    db = db or Database(LOGGER)

    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]
    backup_file = backup_dir.joinpath(f"backup-{database}-{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")
    LOGGER.debug(f"Backup file path: {backup_file}")

    # Pre-flight: ensure there is enough free space before starting the dump.
    db_path_for_check = Path(database_url.database) if database == "sqlite" else None
    if not check_disk_space(database, db, backup_dir, db_path=db_path_for_check):
        sys_exit(1)

    # Get table names from the SQLAlchemy model
    model_tables = list(Base.metadata.tables.keys())
    LOGGER.info(f"Backing up {len(model_tables)} tables defined in the model")

    for attempt in range(1, DUMP_ATTEMPTS + 1):
        if database == "sqlite":
            db_path = Path(database_url.database)

            LOGGER.info("Creating a backup for the SQLite database ...")

            # sqlite3 .dump takes no exclusion and a table list drops indexes, views, triggers and sequences:
            # dump a consistent snapshot of the whole database after removing the write probes from it
            with TemporaryDirectory() as tmp_dir:
                snapshot = Path(tmp_dir, "snapshot.sqlite3")
                with closing(sqlite_connect(db_path.as_posix())) as source, closing(sqlite_connect(snapshot.as_posix())) as copy:
                    source.backup(copy)
                    for (table,) in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
                        if TEST_TABLE_PATTERN.fullmatch(table):
                            copy.execute(f'DROP TABLE "{table}"')
                    copy.commit()
                proc = run(
                    ["sqlite3", snapshot.as_posix(), ".dump"],
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
        else:
            url = make_url(db.database_uri)
            db_user = url.username or ""
            db_password = url.password or ""
            db_host = url.host or ""
            db_port = str(url.port) if url.port else ""
            db_database_name = url.database or ""
            db_query_args = url.query if hasattr(url, "query") else {}

            if database in ("mariadb", "mysql"):
                LOGGER.info("Creating a backup for the MariaDB/MySQL database ...")

                dump_bin, mariadb_client = mysql_client_command("dump")
                inspector = inspect(db.sql_engine)
                cmd = [
                    dump_bin,
                    "-h",
                    db_host,
                    "-u",
                    db_user,
                    db_database_name,
                    # Name the tables and views to dump: a write probe listed by the server can be dropped before the dump reads it.
                    # Triggers, and routines and events where requested below, are still dumped with them.
                    *(name for name in (*inspector.get_table_names(), *inspector.get_view_names()) if not TEST_TABLE_PATTERN.fullmatch(name)),
                ]
                if db_port:
                    cmd.extend(["-P", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend(
                    [
                        "--single-transaction",  # Consistent backup for InnoDB
                        "--triggers",  # Include triggers
                        "--events",  # Include events
                        "--no-tablespaces",  # Avoid requiring the global PROCESS privilege
                        "--max_allowed_packet=2147483648",  # 2GB max packet size
                        "--quick",  # Retrieve rows one at a time
                        "--lock-tables=false",  # Don't lock tables
                        "--skip-add-locks",  # Don't add LOCK TABLES statements
                        "--default-character-set=utf8mb4",  # Use utf8mb4 charset
                        "--add-drop-table",  # Ensure DROP TABLE before CREATE
                    ]
                )

                if database == "mariadb":
                    cmd.append("--routines")  # Include stored procedures and functions (MariaDB only, mariadb-dump sends MariaDB-only queries to MySQL)

                # Avoid --set-gtid-purged for broad compatibility (MariaDB variant doesn't support it)

                cmd.extend(mysql_connection_args(db_query_args, mariadb_client))

                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"MYSQL_PWD": db_password, "PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
            elif database == "postgresql":
                LOGGER.info("Creating a backup for the PostgreSQL database ...")

                cmd = [
                    "pg_dump",
                    "-h",
                    db_host,
                    "-U",
                    db_user,
                    db_database_name,
                    "-w",
                    "--no-password",
                ]
                if db_port:
                    cmd.extend(["-p", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend(
                    [
                        "--clean",  # Include DROP statements for existing objects
                        "--if-exists",  # Avoid errors if objects do not exist
                        "--no-owner",  # Skip ownership commands
                        "--no-privileges",  # Skip privilege commands
                        "--format=plain",  # Plain text format
                        f"--exclude-table={POSTGRESQL_TEST_TABLE_PATTERN}",  # Skip the write probes
                        "--verbose",  # Verbose output for debugging
                    ]
                )

                # Apply additional arguments from query parameters
                pg_env = {"PGPASSWORD": db_password}
                for key, value in db_query_args.items():
                    if key == "sslmode":
                        pg_env["PGSSLMODE"] = value
                    elif key == "sslrootcert":
                        pg_env["PGSSLROOTCERT"] = value
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env,
                )
            elif database == "oracle":
                LOGGER.warning("Creating a database backup for Oracle is not supported")
                return db

        if proc.returncode == 0:
            break

        # A write probe dropped between the table listing and its dump is the only transient failure worth retrying
        stderr = proc.stderr.decode(errors="replace") if proc.stderr else ""
        if attempt == DUMP_ATTEMPTS or not TEST_TABLE_PATTERN.search(stderr):
            LOGGER.error(f"Failed to dump the database: {stderr}")
            sys_exit(1)

    dump_size = len(proc.stdout) if proc.stdout else 0
    sql_name = backup_file.with_suffix(".sql").name
    LOGGER.info(f"Computing SHA-256 checksum of dump ({dump_size} bytes) ...")
    checksum = sha256(proc.stdout).hexdigest()
    LOGGER.info(f"SHA-256 of dump: {checksum}")

    with ZipFile(backup_file, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr(sql_name, proc.stdout)
        zipf.writestr(sql_name + ".sha256", f"{checksum}  {sql_name}\n")

    backup_file.chmod(0o600)
    compressed_size = backup_file.stat().st_size
    LOGGER.info(f"💾 Backup {backup_file.name} created successfully in {backup_dir} ({compressed_size:,} bytes)")
    return db, backup_file


def check_backup_engine(backup_file: Path, database: str) -> str:
    """Return why the archive cannot be restored into `database`, or an empty string when it can.

    A dump is only valid for the engine that wrote it (backup-<engine>-<date>.zip holding backup-<engine>-<date>.sql),
    and this must be known before the tables are dropped.
    """
    stem = backup_file.stem.split("-")
    source = stem[1] if len(stem) > 2 and stem[0] == "backup" else ""
    if source != database:
        return f"it was taken from {source or 'an unknown'} database engine, not {database}"

    sql_name = backup_file.with_suffix(".sql").name
    try:
        with ZipFile(backup_file, "r") as zipf:
            if sql_name not in zipf.namelist():
                return f"it does not contain {sql_name}"
            # Reads every member: a damaged payload must be found before the tables are dropped
            corrupted = zipf.testzip()
            if corrupted:
                return f"its member {corrupted} is corrupted"
    except (BadZipFile, OSError, EOFError, zlib_error) as e:
        return f"it cannot be read: {e}"
    return ""


def verify_backup_checksum(backup_file: Path) -> bool:
    """Verify the SHA-256 checksum of the SQL dump inside a backup zip.

    Returns True if the checksum matches or if no .sha256 file is present
    (backwards compatibility with backups created before checksums were added).
    Returns False if the checksum does not match.
    """
    sql_name = backup_file.with_suffix(".sql").name
    sha256_name = sql_name + ".sha256"

    try:
        with ZipFile(backup_file, "r") as zipf:
            if sha256_name not in zipf.namelist():
                LOGGER.warning(f"{backup_file.name}: no checksum file found (backup predates checksum support), skipping verification.")
                return True

            stored_line = zipf.read(sha256_name).decode().strip()
            stored_checksum = stored_line.split()[0] if stored_line else ""
            sql_data = zipf.read(sql_name)
    except Exception as exc:
        LOGGER.error(f"{backup_file.name}: could not read backup archive: {exc}")
        return False

    computed_checksum = sha256(sql_data).hexdigest()

    if computed_checksum != stored_checksum:
        LOGGER.error(f"{backup_file.name}: checksum MISMATCH — stored={stored_checksum}, computed={computed_checksum}")
        return False

    LOGGER.info(f"{backup_file.name}: checksum OK ({computed_checksum})")
    return True


def restore_database(backup_file: Path, db: Database = None) -> Database:
    """Restore the database from a backup."""
    db = db or Database(LOGGER)
    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]

    refusal = check_backup_engine(backup_file, database)
    if refusal:
        LOGGER.error(f"Refusing to restore {backup_file}, {refusal}. The database was left untouched")
        sys_exit(1)

    # Verify checksum before touching the live database.
    LOGGER.info(f"Verifying checksum of {backup_file.name} ...")
    if not verify_backup_checksum(backup_file):
        if getenv("BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE", "no") == "yes":
            LOGGER.warning("Checksum verification failed but BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes — proceeding with restore anyway.")
        else:
            LOGGER.error("Aborting restore: checksum verification failed. The database was left untouched")
            LOGGER.error("To force restore despite a checksum mismatch, set BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes (use only as a last resort).")
            sys_exit(1)

    Base.metadata.drop_all(db.sql_engine)

    if database == "sqlite":
        db_path = Path(database_url.database)

        # Clear the database
        proc = run(
            ["sqlite3", db_path.as_posix(), ".read", "/dev/null"],
            stdout=PIPE,
            stderr=PIPE,
            env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
        )

        LOGGER.info("Restoring the SQLite database ...")

        tmp_file = Path(sep, "var", "tmp", "bunkerweb", backup_file.with_suffix(".sql").name)
        with ZipFile(backup_file, "r") as zipf:
            # Uncapped: the database is already cleared, so refusing a large (legitimate) dump here
            # would lose it. The file is a local backup, not a download or an upload.
            safe_zip_extractall(zipf, tmp_file.parent, capped=False)

        proc = run(
            ["sqlite3", db_path.as_posix(), f".read {tmp_file.as_posix()}"],
            stdout=PIPE,
            stderr=PIPE,
            env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
        )
        tmp_file.unlink(missing_ok=True)
        Path(str(tmp_file) + ".sha256").unlink(missing_ok=True)
    else:
        url = make_url(db.database_uri)
        db_user = url.username or ""
        db_password = url.password or ""
        db_host = url.host or ""
        db_port = str(url.port) if url.port else ""
        db_database_name = url.database or ""
        db_query_args = url.query if hasattr(url, "query") else {}

        if database in ("mariadb", "mysql"):
            LOGGER.info("Restoring the MariaDB/MySQL database ...")

            restore_bin, mariadb_client = mysql_client_command("restore")
            cmd = [restore_bin, "-h", db_host, "-u", db_user, db_database_name]
            if db_port:
                cmd.extend(["-P", db_port])

            cmd.extend(mysql_connection_args(db_query_args, mariadb_client))

            with ZipFile(backup_file, "r") as zipf:
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", ""), "MYSQL_PWD": db_password},
                    input=zipf.read(backup_file.with_suffix(".sql").name),
                )
        elif database == "postgresql":
            LOGGER.info("Restoring the PostgreSQL database ...")

            cmd = [
                "psql",
                "-h",
                db_host,
                "-U",
                db_user,
                db_database_name,
                "-v",
                "ON_ERROR_STOP=1",  # Stop immediately on error
                "--single-transaction",  # All-or-nothing restore
                "--no-psqlrc",  # Do not read user startup files
                "-X",  # Do not read ~/.psqlrc or ~/.pgpass implicitly
            ]
            if db_port:
                cmd.extend(["-p", db_port])

            # Apply additional arguments from query parameters
            pg_env = {"PGPASSWORD": db_password}
            for key, value in db_query_args.items():
                if key == "sslmode":
                    pg_env["PGSSLMODE"] = value
                elif key == "sslrootcert":
                    pg_env["PGSSLROOTCERT"] = value

            with ZipFile(backup_file, "r") as zipf:
                sql_name = backup_file.with_suffix(".sql").name
                sql_data = zipf.read(sql_name)

                # Sanitize dump for cross-version compatibility:
                # - Remove SET directives unknown to older servers (e.g., transaction_timeout)
                sql_text = sql_data.decode("utf-8", errors="ignore")
                set_blacklist = re.compile(r"^\s*SET\s+(transaction_timeout|idle_session_timeout)\s*=.*;\s*$", re.IGNORECASE)
                sanitized_lines = [line for line in sql_text.splitlines(True) if not set_blacklist.match(line)]
                sanitized_sql = "".join(sanitized_lines).encode()

                # Stabilize restore by setting safe defaults before feeding dump
                # Avoid superuser-only settings to preserve compatibility
                preamble = (
                    "SET client_min_messages = WARNING;\n"
                    "SET statement_timeout = 0;\n"
                    "SET lock_timeout = '5s';\n"
                    "SET idle_in_transaction_session_timeout = '5min';\n"
                    "SET client_encoding = 'UTF8';\n"
                    "SET standard_conforming_strings = on;\n"
                    "SET search_path = public, pg_catalog;\n"
                ).encode()
                input_bytes = preamble + sanitized_sql

                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    input=input_bytes,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env,
                )
        elif database == "oracle":
            LOGGER.warning("Restoring a database backup for Oracle is not supported")
            return db

    if proc.returncode != 0:
        LOGGER.error(f"Failed to restore the database: {proc.stderr.decode()}")
        sys_exit(1)

    err = db.checked_changes(plugins_changes="all", value=True)
    if err:
        LOGGER.error(f"Error while applying changes to the database: {err}, you may need to reload the application")

    LOGGER.info(f"💾 Database restored successfully from {backup_file}")
    return db
