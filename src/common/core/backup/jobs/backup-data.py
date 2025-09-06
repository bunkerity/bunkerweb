#!/usr/bin/env python3

from datetime import datetime, timedelta
from json import loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",), ("core", "backup"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore
from backup import backup_database, update_cache_file, acquire_db_lock, DB_LOCK_FILE

LOGGER = setup_logger("BACKUP")
status = 0

try:
    # Prevent concurrent DB access with other backup plugins
    acquire_db_lock()
    backup_dir = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    force_backup = getenv("FORCE_BACKUP", "no") == "yes"
    current_time = datetime.now().astimezone()

    if not force_backup:
        # Check if backup is activated
        if getenv("USE_BACKUP", "yes") == "no":
            LOGGER.info("Backup feature is disabled, skipping backup ...")
            sys_exit(0)

        JOB = Job(LOGGER, __file__)

        last_backup = loads(JOB.get_cache("backup.json") or "{}")
        last_backup_date = last_backup.get("date", None)
        if last_backup_date:
            last_backup_date = datetime.fromisoformat(last_backup_date).astimezone()

        backup_period = getenv("BACKUP_SCHEDULE", "daily")
        PERIOD_STAMPS = {
            "daily": timedelta(days=1).total_seconds(),
            "weekly": timedelta(weeks=1).total_seconds(),
            "monthly": timedelta(weeks=4).total_seconds(),
        }

        already_done = last_backup_date and last_backup_date.timestamp() + PERIOD_STAMPS[backup_period] > current_time.timestamp()
        backup_rotation = int(getenv("BACKUP_ROTATION", "7"))

        sorted_files = []
        if already_done:

            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)

        if len(sorted_files) <= backup_rotation and already_done:
            LOGGER.info(f"Backup already done within the last {backup_period} period, skipping backup ...")
            sys_exit(0)

        db = JOB.db
    else:
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    backed_up = False
    if force_backup or not already_done:
        if not force_backup:
            db_metadata = db.get_metadata()

            if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
                LOGGER.info("First start of the scheduler, skipping backup ...")
                sys_exit(0)

        db, _ = backup_database(current_time, db, backup_dir)
        backed_up = True

        if not force_backup:
            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)

    if not force_backup:
        # Check if the number of backup files exceeds the rotation limit
        if len(sorted_files) > backup_rotation:
            # Calculate the number of files to remove
            num_files_to_remove = len(sorted_files) - backup_rotation

            # Remove the oldest backup files
            for file in sorted_files[:num_files_to_remove]:
                LOGGER.warning(f"Removing old backup file: {file}, as the rotation limit has been reached ...")
                file.unlink()

        if backed_up:
            update_cache_file(db, backup_dir)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running backup-data.py :\n{e}")

finally:
    # Always release DB lock
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
