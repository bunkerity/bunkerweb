#!/usr/bin/env python3

from datetime import datetime, timedelta
from json import loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",), ("core", "backup"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="backup-data",
    log_file_path="/var/log/bunkerweb/backup.log"
)

logger.debug("Debug mode enabled for backup")

from Database import Database  # type: ignore
from jobs import Job  # type: ignore
from backup import backup_database, update_cache_file

status = 0

try:
    backup_dir = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Backup directory: {backup_dir}")

    force_backup = getenv("FORCE_BACKUP", "no") == "yes"
    current_time = datetime.now().astimezone()
    logger.debug(f"Force backup: {force_backup}, Current time: {current_time}")

    if not force_backup:
        # Check if backup is activated
        if getenv("USE_BACKUP", "yes") == "no":
            logger.info("Backup feature is disabled, skipping backup ...")
            sys_exit(0)

        JOB = Job(logger, __file__)
        logger.debug("Job instance created")

        last_backup = loads(JOB.get_cache("backup.json") or "{}")
        last_backup_date = last_backup.get("date", None)
        if last_backup_date:
            last_backup_date = datetime.fromisoformat(last_backup_date).astimezone()
        logger.debug(f"Last backup date: {last_backup_date}")

        backup_period = getenv("BACKUP_SCHEDULE", "daily")
        PERIOD_STAMPS = {
            "daily": timedelta(days=1).total_seconds(),
            "weekly": timedelta(weeks=1).total_seconds(),
            "monthly": timedelta(weeks=4).total_seconds(),
        }
        logger.debug(f"Backup period: {backup_period}")

        already_done = last_backup_date and last_backup_date.timestamp() + PERIOD_STAMPS[backup_period] > current_time.timestamp()
        backup_rotation = int(getenv("BACKUP_ROTATION", "7"))
        logger.debug(f"Already done: {already_done}, Backup rotation: {backup_rotation}")

        sorted_files = []
        if already_done:

            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            logger.debug(f"Found {len(sorted_files)} existing backup files")

        if len(sorted_files) <= backup_rotation and already_done:
            logger.info(f"Backup already done within the last {backup_period} period, skipping backup ...")
            sys_exit(0)

        db = JOB.db
    else:
        db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"))
        logger.debug("Database instance created for forced backup")

    backed_up = False
    if force_backup or not already_done:
        if not force_backup:
            db_metadata = db.get_metadata()
            logger.debug(f"Database metadata: {db_metadata}")

            if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
                logger.info("First start of the scheduler, skipping backup ...")
                sys_exit(0)

        logger.debug("Starting backup process")
        backup_database(current_time, db, backup_dir)
        backed_up = True
        logger.debug("Backup completed successfully")

        if not force_backup:
            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            logger.debug(f"Updated file list: {len(sorted_files)} backup files")

    if not force_backup:
        # Check if the number of backup files exceeds the rotation limit
        if len(sorted_files) > backup_rotation:
            # Calculate the number of files to remove
            num_files_to_remove = len(sorted_files) - backup_rotation
            logger.debug(f"Need to remove {num_files_to_remove} old backup files")

            # Remove the oldest backup files
            for file in sorted_files[:num_files_to_remove]:
                logger.warning(f"Removing old backup file: {file}, as the rotation limit has been reached ...")
                file.unlink()

        if backed_up:
            logger.debug("Updating cache file")
            update_cache_file(db, backup_dir)
            
except SystemExit as e:
    status = e.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    status = 2
    logger.exception("Exception while running backup-data.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
