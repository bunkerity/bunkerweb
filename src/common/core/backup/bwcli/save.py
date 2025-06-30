#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os import getenv
from os.path import join, sep
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import (acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, 
                    LOGGER, update_cache_file)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "").lower() == "debug"

status = 0

try:
    # Acquire database lock to prevent concurrent access
    acquire_db_lock()
    
    if DEBUG_MODE:
        LOGGER.debug("Database lock acquired for save command")

    # Global parser for command line arguments
    parser = ArgumentParser(
        description="BunkerWeb's backup plugin save command line interface"
    )

    # Optional directory argument for backup location
    parser.add_argument(
        "-d",
        "--directory",
        default=BACKUP_DIR,
        type=str,
        help="directory where to save the backup, default is the one "
             "defined in the setting BACKUP_DIRECTORY",
    )

    # Parse command line arguments
    args = parser.parse_args()
    
    if DEBUG_MODE:
        LOGGER.debug(f"Parsed arguments: {vars(args)}")

    directory = Path(args.directory)

    LOGGER.debug(f"Backup directory: {directory}")
    
    if DEBUG_MODE:
        LOGGER.debug(f"Directory exists: {directory.exists()}")
        LOGGER.debug(f"Directory is dir: {directory.is_dir()}")

    # Validate and create backup directory if needed
    if not directory.is_dir():
        if directory == BACKUP_DIR:
            LOGGER.error(f"Backup directory {directory} does not exist")
            sys_exit(1)

        LOGGER.info(f"Creating directory {directory} as it does not exist")
        
        if DEBUG_MODE:
            LOGGER.debug(f"Creating directory with parents=True: {directory}")
        
        directory.mkdir(parents=True, exist_ok=True)

    # Create backup with current timestamp
    current_time = datetime.now().astimezone()
    
    if DEBUG_MODE:
        LOGGER.debug(f"Starting backup at: {current_time}")
    
    db = backup_database(current_time, backup_dir=directory)

    # Update cache file if using default backup directory
    if directory == BACKUP_DIR:
        if DEBUG_MODE:
            LOGGER.debug("Updating cache file for default backup directory")
        update_cache_file(db, directory)
    
    if DEBUG_MODE:
        LOGGER.debug("Save command completed successfully")

except SystemExit as se:
    status = se.code
    if DEBUG_MODE:
        LOGGER.debug(f"SystemExit caught with code: {status}")
        
except BaseException as e:
    LOGGER.error(f"Error while executing backup save command: {e}")
    status = 1
    
    if DEBUG_MODE:
        LOGGER.debug(f"BaseException caught: {type(e).__name__}")
        LOGGER.debug(f"Exception details: {str(e)}")

finally:
    # Always release database lock
    if DEBUG_MODE:
        LOGGER.debug("Releasing database lock")
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)