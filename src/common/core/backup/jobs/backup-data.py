#!/usr/bin/env python3

from datetime import datetime, timedelta
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import PIPE, run
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore


LOGGER = setup_logger("BACKUP", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Check if backup is activated
    if getenv("USE_BACKUP", "yes") == "no":
        LOGGER.info("Backup feature is disabled, skipping backup ...")
        sys_exit(0)

    backup_dir = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))

    JOB = Job(LOGGER)

    last_backup = JOB.get_cache("last_backup.txt")
    if last_backup:
        last_backup = datetime.fromisoformat(last_backup.decode())

    current_time = datetime.now()
    backup_period = getenv("BACKUP_SCHEDULE", "daily")
    PERIOD_STAMPS = {
        "daily": timedelta(days=1).total_seconds(),
        "weekly": timedelta(weeks=1).total_seconds(),
        "monthly": timedelta(weeks=4).total_seconds(),
    }

    if last_backup and last_backup.timestamp() + PERIOD_STAMPS[backup_period] > current_time.timestamp():
        LOGGER.info(f"Backup already done within the last {backup_period} period, skipping backup ...")
        sys_exit(0)

    with Lock():
        is_scheduler_first_start = JOB.db.is_scheduler_first_start()

    if is_scheduler_first_start:
        LOGGER.info("First start of the scheduler, skipping backup ...")
        sys_exit(0)

    database: Literal["sqlite", "mariadb", "mysql", "postgresql"] = JOB.db.database_uri.split(":")[0].split("+")[0]
    backup_file = backup_dir.joinpath(f"backup-{database}-{current_time.strftime('%Y-%m-%d')}.zip")
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.debug(f"Backup file path: {backup_file}")

    if database == "sqlite":
        match = JOB.db.DB_STRING_RX.search(JOB.db.database_uri)
        if not match:
            LOGGER.error(f"Invalid database string provided: {JOB.db.database_uri}, skipping backup ...")
            sys_exit(1)

        db_path = Path(match.group("path"))

        LOGGER.info("Creating a backup for the SQLite database ...")

        proc = run(["sqlite3", db_path.as_posix(), ".dump"], stdout=PIPE, stderr=PIPE)
    else:
        db_host = JOB.db.database_uri.rsplit("@", 1)[1].split("/")[0].split(":")
        db_port = None
        if len(db_host) == 1:
            db_host = db_host[0]
        else:
            db_host, db_port = db_host

        db_user = JOB.db.database_uri.split("://")[1].split(":")[0]
        db_password = JOB.db.database_uri.split("://")[1].split(":")[1].rsplit("@", 1)[0]
        db_database_name = JOB.db.database_uri.split("/")[-1]

        if database in ("mariadb", "mysql"):
            LOGGER.info("Creating a backup for the MariaDB/MySQL database ...")

            proc = run(["mysqldump", "-h", db_host, "-u", db_user, db_database_name], stdout=PIPE, stderr=PIPE, env=environ | {"MYSQL_PWD": db_password})
        elif database == "postgresql":
            LOGGER.info("Creating a backup for the PostgreSQL database ...")

            proc = run(
                ["pg_dump", "-h", db_host, "-U", db_user, "-d", db_database_name, "-w"], stdout=PIPE, stderr=PIPE, env=environ | {"PGPASSWORD": db_password}
            )

    if proc.returncode != 0:
        LOGGER.error(f"Failed to dump the database: {proc.stderr.decode()}")
        sys_exit(1)

    with ZipFile(backup_file, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr(backup_file.with_suffix(".sql").name, proc.stdout)

    backup_rotation = int(getenv("BACKUP_ROTATION", "7"))

    # Get all backup files in the directory
    backup_files = backup_dir.glob("backup-*.zip")

    # Sort the backup files by name
    sorted_files = sorted(backup_files)

    # Check if the number of backup files exceeds the rotation limit
    if len(sorted_files) > backup_rotation:
        # Calculate the number of files to remove
        num_files_to_remove = len(sorted_files) - backup_rotation

        # Remove the oldest backup files
        for file in sorted_files[:num_files_to_remove]:
            LOGGER.warning(f"Removing old backup file: {file}, as the rotation limit has been reached ...")
            file.unlink()

    cached, err = JOB.cache_file("last_backup.txt", current_time.isoformat().encode())
    if not cached:
        LOGGER.error(f"Failed to cache last_backup.txt :\n{err}")
        status = 2
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running backup-data.py :\n{format_exc()}")

sys_exit(status)
