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


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


status = 0

try:
    # Acquire database lock to prevent concurrent access
    acquire_db_lock()
    
    debug_log(LOGGER, "Database lock acquired for save command")

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
    
    debug_log(LOGGER, f"Parsed arguments: {vars(args)}")

    directory = Path(args.directory)

    LOGGER.debug(f"Backup directory: {directory}")
    
    debug_log(LOGGER, f"Directory exists: {directory.exists()}")
    debug_log(LOGGER, f"Directory is dir: {directory.is_dir()}")

    # Validate and create backup directory if needed
    if not directory.is_dir():
        if directory == BACKUP_DIR:
            LOGGER.error(f"Backup directory {directory} does not exist")
            sys_exit(1)

        LOGGER.info(f"Creating directory {directory} as it does not exist")
        
        debug_log(LOGGER, f"Creating directory with parents=True: {directory}")
        
        directory.mkdir(parents=True, exist_ok=True)

    # Create backup with current timestamp
    current_time = datetime.now().astimezone()
    
    debug_log(LOGGER, f"Starting backup at: {current_time}")
    
    db = backup_database(current_time, backup_dir=directory)

    # Update cache file if using default backup directory
    if directory == BACKUP_DIR:
        debug_log(LOGGER, "Updating cache file for default backup directory")
        update_cache_file(db, directory)
    
    debug_log(LOGGER, "Save command completed successfully")

except SystemExit as se:
    status = se.code
    debug_log(LOGGER, f"SystemExit caught with code: {status}")
        
except BaseException as e:
    LOGGER.error(f"Error while executing backup save command: {e}")
    status = 1
    
    debug_log(LOGGER, f"BaseException caught: {type(e).__name__}")
    debug_log(LOGGER, f"Exception details: {str(e)}")

finally:
    # Always release database lock
    debug_log(LOGGER, "Releasing database lock")
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)