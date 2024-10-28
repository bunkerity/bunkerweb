#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from os import environ, getenv
from os.path import join, sep
from pathlib import Path
from re import compile as re_compile
from subprocess import PIPE, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from model import Base  # type: ignore

LOGGER = setup_logger("BACKUP", getenv("LOG_LEVEL", "INFO"))

DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?):/+(?P<path>/[^\s]+)")
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


def backup_database(current_time: datetime, db: Database = None, backup_dir: Path = BACKUP_DIR) -> Database:
    """Backup the database."""
    db = db or Database(LOGGER)

    database: Literal["sqlite", "mariadb", "mysql", "postgresql"] = db.database_uri.split(":")[0].split("+")[0]  # type: ignore
    backup_file = backup_dir.joinpath(f"backup-{database}-{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")
    LOGGER.debug(f"Backup file path: {backup_file}")
    stderr = "Table 'db.test_"
    current_time = datetime.now().astimezone()

    while "Table 'db.test_" in stderr and (datetime.now().astimezone() - current_time).total_seconds() < 10:
        if database == "sqlite":
            match = DB_STRING_RX.search(db.database_uri)
            if not match:
                LOGGER.error(f"Invalid database string provided: {db.database_uri}, skipping backup ...")
                sys_exit(1)

            db_path = Path(match.group("path"))

            LOGGER.info("Creating a backup for the SQLite database ...")

            proc = run(["sqlite3", db_path.as_posix(), ".dump"], stdout=PIPE, stderr=PIPE)
        else:
            db_host = db.database_uri.rsplit("@", 1)[1].split("/")[0].split(":")
            db_port = None
            if len(db_host) == 1:
                db_host = db_host[0]
            else:
                db_host, db_port = db_host

            db_user = db.database_uri.split("://")[1].split(":")[0]
            db_password = db.database_uri.split("://")[1].split(":")[1].rsplit("@", 1)[0]
            db_database_name = db.database_uri.split("/")[-1].split("?")[0]

            if database in ("mariadb", "mysql"):
                LOGGER.info("Creating a backup for the MariaDB/MySQL database ...")

                cmd = ["mysqldump" if database == "mysql" else "mariadb-dump", "-h", db_host, "-u", db_user, db_database_name]
                if db_port:
                    cmd.extend(["-P", db_port])

                proc = run(cmd, stdout=PIPE, stderr=PIPE, env=environ | {"MYSQL_PWD": db_password})
            elif database == "postgresql":
                LOGGER.info("Creating a backup for the PostgreSQL database ...")

                cmd = ["pg_dump", "-h", db_host, "-U", db_user, db_database_name, "-w"]
                if db_port:
                    cmd.extend(["-p", db_port])

                proc = run(cmd, stdout=PIPE, stderr=PIPE, env=environ | {"PGPASSWORD": db_password})

        stderr = proc.stderr.decode()
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
    return db


def restore_database(backup_file: Path, db: Database = None) -> Database:
    """Restore the database from a backup."""
    db = db or Database(LOGGER)
    Base.metadata.drop_all(db.sql_engine)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql"] = db.database_uri.split(":")[0].split("+")[0]  # type: ignore

    if database == "sqlite":
        match = DB_STRING_RX.search(db.database_uri)
        if not match:
            LOGGER.error(f"Invalid database string provided: {db.database_uri}, skipping restore ...")
            sys_exit(1)

        db_path = Path(match.group("path"))

        # Clear the database
        proc = run(["sqlite3", db_path.as_posix(), ".read", "/dev/null"], stdout=PIPE, stderr=PIPE)

        LOGGER.info("Restoring the SQLite database ...")

        tmp_file = Path(sep, "var", "tmp", "bunkerweb", backup_file.with_suffix(".sql").name)
        with ZipFile(backup_file, "r") as zipf:
            zipf.extractall(path=tmp_file.parent)

        proc = run(["sqlite3", db_path.as_posix(), f".read {tmp_file.as_posix()}"], stdout=PIPE, stderr=PIPE)
        tmp_file.unlink(missing_ok=True)
    else:
        db_host = db.database_uri.rsplit("@", 1)[1].split("/")[0].split(":")
        db_port = None
        if len(db_host) == 1:
            db_host = db_host[0]
        else:
            db_host, db_port = db_host

        db_user = db.database_uri.split("://")[1].split(":")[0]
        db_password = db.database_uri.split("://")[1].split(":")[1].rsplit("@", 1)[0]
        db_database_name = db.database_uri.split("/")[-1].split("?")[0]

        if database in ("mariadb", "mysql"):
            LOGGER.info("Restoring the MariaDB/MySQL database ...")

            cmd = ["mysql", "-h", db_host, "-u", db_user, db_database_name]
            if db_port:
                cmd.extend(["-P", db_port])

            with ZipFile(backup_file, "r") as zipf:
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env=environ | {"MYSQL_PWD": db_password},
                    input=zipf.read(backup_file.with_suffix(".sql").name),
                )
        elif database == "postgresql":
            LOGGER.info("Restoring the PostgreSQL database ...")

            cmd = ["psql", "-h", db_host, "-U", db_user, db_database_name]
            if db_port:
                cmd.extend(["-p", db_port])

            with ZipFile(backup_file, "r") as zipf:
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env=environ | {"PGPASSWORD": db_password},
                    input=zipf.read(backup_file.with_suffix(".sql").name),
                )

    if proc.returncode != 0:
        LOGGER.error(f"Failed to restore the database: {proc.stderr.decode()}")
        sys_exit(1)

    err = db.checked_changes(plugins_changes="all", value=True)
    if err:
        LOGGER.error(f"Error while applying changes to the database: {err}, you may need to reload the application")

    LOGGER.info(f"💾 Database restored successfully from {backup_file}")
    return db
