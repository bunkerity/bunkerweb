#!/usr/bin/env python3

from datetime import datetime
import re
from json import dumps, loads
from os import getenv
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, run
from shutil import which
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Literal
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
    stderr = "Table 'db.test_"
    current_time = datetime.now().astimezone()

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

    with ZipFile(backup_file, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr(backup_file.with_suffix(".sql").name, proc.stdout)

    backup_file.chmod(0o600)

    LOGGER.info(f"💾 Backup {backup_file.name} created successfully in {backup_dir}")
    return db, backup_file


def restore_database(backup_file: Path, db: Database = None) -> Database:
    """Restore the database from a backup."""
    db = db or Database(LOGGER)
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
