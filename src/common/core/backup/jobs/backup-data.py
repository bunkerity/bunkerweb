#!/usr/bin/env python3

from datetime import datetime, timedelta
from json import loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",), 
                               ("core", "backup"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore
from backup import backup_database, update_cache_file

LOGGER = setup_logger("BACKUP")
status = 0

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "").lower() == "debug"

try:
    # Setup backup directory from environment variable
    backup_dir = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    if DEBUG_MODE:
        LOGGER.debug(f"Backup directory: {backup_dir}")
        LOGGER.debug(f"Directory exists: {backup_dir.exists()}")

    # Check if this is a forced backup operation
    force_backup = getenv("FORCE_BACKUP", "no") == "yes"
    current_time = datetime.now().astimezone()
    
    if DEBUG_MODE:
        LOGGER.debug(f"Force backup: {force_backup}")
        LOGGER.debug(f"Current time: {current_time}")

    if not force_backup:
        # Check if backup feature is enabled
        if getenv("USE_BACKUP", "yes") == "no":
            LOGGER.info("Backup feature is disabled, skipping backup ...")
            if DEBUG_MODE:
                LOGGER.debug("USE_BACKUP environment variable is set to 'no'")
            sys_exit(0)

        # Initialize job context
        JOB = Job(LOGGER, __file__)
        
        if DEBUG_MODE:
            LOGGER.debug("Job instance created successfully")

        # Get last backup information from cache
        last_backup = loads(JOB.get_cache("backup.json") or "{}")
        last_backup_date = last_backup.get("date", None)
        
        if DEBUG_MODE:
            LOGGER.debug(f"Last backup data: {last_backup}")
            LOGGER.debug(f"Last backup date string: {last_backup_date}")
        
        if last_backup_date:
            last_backup_date = datetime.fromisoformat(
                last_backup_date
            ).astimezone()
            if DEBUG_MODE:
                LOGGER.debug(f"Last backup date parsed: {last_backup_date}")

        # Get backup schedule configuration
        backup_period = getenv("BACKUP_SCHEDULE", "daily")
        
        # Define backup period intervals in seconds
        PERIOD_STAMPS = {
            "daily": timedelta(days=1).total_seconds(),
            "weekly": timedelta(weeks=1).total_seconds(),
            "monthly": timedelta(weeks=4).total_seconds(),
        }
        
        if DEBUG_MODE:
            LOGGER.debug(f"Backup period: {backup_period}")
            LOGGER.debug(f"Period stamp: {PERIOD_STAMPS[backup_period]} seconds")

        # Check if backup is already done within the specified period
        already_done = (last_backup_date and 
                       last_backup_date.timestamp() + 
                       PERIOD_STAMPS[backup_period] > current_time.timestamp())
        
        backup_rotation = int(getenv("BACKUP_ROTATION", "7"))
        
        if DEBUG_MODE:
            LOGGER.debug(f"Already done: {already_done}")
            LOGGER.debug(f"Backup rotation: {backup_rotation}")

        sorted_files = []
        if already_done:
            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")
            
            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            
            if DEBUG_MODE:
                LOGGER.debug(f"Found {len(sorted_files)} backup files")
                LOGGER.debug(f"Backup files: "
                           f"{[f.name for f in sorted_files]}")

        # Skip backup if already done and within rotation limit
        if len(sorted_files) <= backup_rotation and already_done:
            LOGGER.info(
                f"Backup already done within the last {backup_period} period, "
                f"skipping backup ..."
            )
            if DEBUG_MODE:
                LOGGER.debug(f"Number of files ({len(sorted_files)}) is within "
                           f"rotation limit ({backup_rotation}) and backup "
                           f"was already done")
            sys_exit(0)

        db = JOB.db
        
        if DEBUG_MODE:
            LOGGER.debug("Database instance obtained from job")
    else:
        # Create database instance for forced backup
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
        
        if DEBUG_MODE:
            LOGGER.debug("Database instance created with custom URI")

    backed_up = False
    
    # Perform backup if forced or not already done
    if force_backup or not already_done:
        if not force_backup:
            # Check database metadata for first start condition
            db_metadata = db.get_metadata()
            
            if DEBUG_MODE:
                LOGGER.debug(f"Database metadata: {db_metadata}")

            if (isinstance(db_metadata, str) or 
                db_metadata["scheduler_first_start"]):
                LOGGER.info(
                    "First start of the scheduler, skipping backup ..."
                )
                if DEBUG_MODE:
                    LOGGER.debug("Scheduler first start detected")
                sys_exit(0)

        # Perform the actual backup
        if DEBUG_MODE:
            LOGGER.debug("Starting backup process")
        
        backup_database(current_time, db, backup_dir)
        backed_up = True
        
        if DEBUG_MODE:
            LOGGER.debug("Backup completed successfully")

        if not force_backup:
            # Get all backup files in the directory after backup
            backup_files = backup_dir.glob("backup-*.zip")
            
            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            
            if DEBUG_MODE:
                LOGGER.debug(f"After backup, found {len(sorted_files)} files")

    if not force_backup:
        # Handle backup rotation - remove old files if exceeding limit
        if len(sorted_files) > backup_rotation:
            # Calculate the number of files to remove
            num_files_to_remove = len(sorted_files) - backup_rotation
            
            if DEBUG_MODE:
                LOGGER.debug(f"Need to remove {num_files_to_remove} old files")

            # Remove the oldest backup files
            for file in sorted_files[:num_files_to_remove]:
                LOGGER.warning(
                    f"Removing old backup file: {file}, as the rotation "
                    f"limit has been reached ..."
                )
                
                if DEBUG_MODE:
                    LOGGER.debug(f"Removing file: {file}")
                    LOGGER.debug(f"File size: {file.stat().st_size} bytes")
                
                file.unlink()

        # Update cache file with current backup information
        if backed_up:
            if DEBUG_MODE:
                LOGGER.debug("Updating cache file with new backup information")
            update_cache_file(db, backup_dir)

except SystemExit as e:
    status = e.code
    if DEBUG_MODE:
        LOGGER.debug(f"SystemExit caught with code: {status}")
        
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running backup-data.py :\n{e}")
    
    if DEBUG_MODE:
        LOGGER.debug(f"BaseException caught: {type(e).__name__}")
        LOGGER.debug(f"Exception details: {str(e)}")

if DEBUG_MODE:
    LOGGER.debug(f"Script exiting with status: {status}")

sys_exit(status)