#!/usr/bin/env python3

from datetime import datetime, timedelta
from hashlib import sha256
import re
from json import dumps, loads
from os import getenv
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, run
from shutil import disk_usage, which
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Callable, List, Literal, Optional, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from sqlalchemy.engine.url import make_url

from common_utils import bytes_hash  # type: ignore
from Database import Database  # type: ignore
from logger import getLogger  # type: ignore
from model import Base  # type: ignore

LOGGER = getLogger("BACKUP")

BACKUP_DIR = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")


def acquire_db_lock():
    """Acquire the database lock to prevent concurrent access to the database."""
    current_time = datetime.now().astimezone()
    while DB_LOCK_FILE.is_file() and DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp():
        LOGGER.warning("Database is locked, waiting for it to be unlocked (timeout: 30s) ...")
        sleep(1)
    DB_LOCK_FILE.unlink(missing_ok=True)
    DB_LOCK_FILE.touch()


def is_sqlite_wal(db: "Database") -> bool:
    """Return True if the database is SQLite running in WAL journal mode.

    In WAL mode SQLite allows concurrent readers alongside an active writer,
    so the backup dump can proceed without acquiring the BunkerWeb lock.
    """
    database_url = make_url(db.database_uri)
    if database_url.drivername.split("+")[0] != "sqlite":
        return False
    try:
        from sqlalchemy import text  # type: ignore[import]  # path set via sys_path at runtime

        with db.sql_engine.connect() as conn:
            row = conn.execute(text("PRAGMA journal_mode")).fetchone()
        return bool(row and str(row[0]).lower() == "wal")
    except Exception as exc:
        LOGGER.debug(f"Could not check SQLite journal mode (assuming non-WAL): {exc}")
        return False


def check_disk_space(database: str, db: "Database", backup_dir: Path, db_path: Optional[Path] = None) -> bool:
    """Check whether backup_dir has enough free space to hold a new backup.

    The estimated dump size uses a 2× multiplier over the raw database size to
    account for SQL text being larger than the on-disk binary representation
    (especially for SQLite). After zip compression the actual backup file will
    be significantly smaller, so this is intentionally conservative.

    Returns True when there is enough space or when the check cannot be
    performed (so the backup is never silently skipped due to a query error).
    """
    try:
        from sqlalchemy import text  # type: ignore[import]  # path set via sys_path at runtime

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


HANOI_TIERS: List[Tuple[int, timedelta]] = [
    (6, timedelta(hours=1)),    # 6 × 1h   → covers last 0–6h ago
    (2, timedelta(hours=2)),    # 2 × 2h   → covers 8+10h ago
    (2, timedelta(hours=4)),    # 2 × 4h   → covers 14+18h ago
    (2, timedelta(hours=8)),    # 2 × 8h   → covers 26+34h ago (~1.1+1.4d)
    (2, timedelta(hours=16)),   # 2 × 16h  → covers 50+66h ago (~2.1+2.75d)
    (2, timedelta(hours=32)),   # 2 × 32h  → covers 98+130h ago (~4.1+5.4d)
    (2, timedelta(hours=64)),   # 2 × 64h  → covers 194+258h ago (~8.1+10.75d)
    (2, timedelta(hours=128)),  # 2 × 128h → covers 386+514h ago (~16.1+21.4d)
    (2, timedelta(hours=256)),  # 2 × 256h → covers 770+1026h ago (~32.1+42.75d)
    (2, timedelta(hours=512)),  # 2 × 512h → covers 1538+2050h ago (~64.1+85.4d)
]


def hanoi_rotation(backup_files: List[Path], now: datetime) -> List[Path]:
    """Return the list of files to DELETE under Towers-of-Hanoi rotation.

    Walks backwards from *now* through the tier slots. For each slot the most
    recent backup that falls within the slot's window is kept. Everything else
    is returned for deletion. Total: 24 files kept, ~85 days of coverage.
    """
    timed: List[Tuple[datetime, Path]] = []
    for f in backup_files:
        m = re.search(r"backup-\w+-(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", f.name)
        if m:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S").astimezone()
            timed.append((dt, f))

    timed.sort(reverse=True)  # newest first

    keep: set = set()
    cursor = now
    for count, interval in HANOI_TIERS:
        for _ in range(count):
            slot_start = cursor - interval
            for dt, f in timed:
                if slot_start < dt <= cursor:
                    keep.add(f)
                    break
            cursor = slot_start

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


def backup_database(current_time: datetime, db: Database = None, backup_dir: Path = BACKUP_DIR, post_dump_hook: Optional[Callable] = None):
    """Backup the database."""
    db = db or Database(LOGGER)

    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]
    backup_file = backup_dir.joinpath(f"backup-{database}-{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")
    LOGGER.debug(f"Backup file path: {backup_file}")
    stderr = "Table 'db.test_"
    current_time = datetime.now().astimezone()

    # Pre-flight: ensure there is enough free space before starting the dump.
    db_path_for_check = Path(database_url.database) if database == "sqlite" else None
    if not check_disk_space(database, db, backup_dir, db_path=db_path_for_check):
        sys_exit(1)

    # Get table names from the SQLAlchemy model
    model_tables = list(Base.metadata.tables.keys())
    LOGGER.info(f"Backing up {len(model_tables)} tables defined in the model")

    while "Table 'db.test_" in stderr and (datetime.now().astimezone() - current_time).total_seconds() < 10:
        if database == "sqlite":
            db_path = Path(database_url.database)

            LOGGER.info("Creating a backup for the SQLite database ...")

            # Full SQLite database dump
            proc = run(
                ["sqlite3", db_path.as_posix()],
                input=".dump\n".encode(),
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

                dump_bin = "mariadb-dump" if which("mariadb-dump") else "mysqldump"
                cmd = [
                    dump_bin,
                    "-h",
                    db_host,
                    "-u",
                    db_user,
                    db_database_name,
                ]
                if db_port:
                    cmd.extend(["-P", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend(
                    [
                        "--single-transaction",  # Consistent backup for InnoDB
                        "--routines",  # Include stored procedures and functions
                        "--triggers",  # Include triggers
                        "--events",  # Include events
                        "--max_allowed_packet=2147483648",  # 2GB max packet size
                        "--quick",  # Retrieve rows one at a time
                        "--lock-tables=false",  # Don't lock tables
                        "--skip-add-locks",  # Don't add LOCK TABLES statements
                        "--default-character-set=utf8mb4",  # Use utf8mb4 charset
                        "--add-drop-table",  # Ensure DROP TABLE before CREATE
                    ]
                )

                # Avoid --set-gtid-purged for broad compatibility (MariaDB variant doesn't support it)

                # Apply additional arguments from query parameters
                for key, value in db_query_args.items():
                    if key == "ssl" and value == "true":
                        cmd.append("--ssl")
                    elif key == "charset":
                        cmd.extend(["--default-character-set", value])

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

        stderr = proc.stderr.decode() if hasattr(proc, "stderr") and proc.stderr else ""
        if "Table 'db.test_" not in stderr and proc.returncode != 0:
            LOGGER.error(f"Failed to dump the database: {stderr}")
            sys_exit(1)

    if (datetime.now().astimezone() - current_time).total_seconds() >= 10:
        LOGGER.error("Failed to dump the database: Timeout reached")
        sys_exit(1)

    dump_size = len(proc.stdout) if proc.stdout else 0
    LOGGER.debug(f"Dump complete: {dump_size} bytes. Running post-dump hook ...")

    if post_dump_hook:
        # Release the DB lock here — after the dump but before compression.
        # Compression (zip) is CPU-bound and does not access the database, so
        # there is no need to hold the lock during it. This reduces the lock
        # hold time from the full dump+compress duration (e.g. ~18 s for a
        # large SQLite database) down to just the dump phase (~2 s), allowing
        # other processes (e.g. concurrent bwcli calls) to proceed sooner.
        post_dump_hook()

    LOGGER.info(f"Database dump complete ({dump_size} bytes), compressing ...")
    LOGGER.debug("Compressing ...")

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

    # Verify checksum before touching the live database.
    LOGGER.info(f"Verifying checksum of {backup_file.name} ...")
    if not verify_backup_checksum(backup_file):
        if getenv("BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE", "no") == "yes":
            LOGGER.warning("Checksum verification failed but BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes — proceeding with restore anyway.")
        else:
            LOGGER.error("Aborting restore: checksum verification failed.")
            LOGGER.error("To force restore despite a checksum mismatch, set BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes (use only as a last resort).")
            sys_exit(1)

    Base.metadata.drop_all(db.sql_engine)
    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]

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
            zipf.extractall(path=tmp_file.parent)

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

            cmd = ["mysql", "-h", db_host, "-u", db_user, db_database_name]
            if db_port:
                cmd.extend(["-P", db_port])

            # Apply additional arguments from query parameters
            for key, value in db_query_args.items():
                if key == "ssl" and value == "true":
                    cmd.append("--ssl")
                elif key == "charset":
                    cmd.extend(["--default-character-set", value])

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
