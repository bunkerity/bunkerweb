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
                    LOGGER, restore_database)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "").lower() == "debug"

status = 0

try:
    # Acquire database lock to prevent concurrent access
    acquire_db_lock()
    
    if DEBUG_MODE:
        LOGGER.debug("Database lock acquired for restore command")

    # Global parser for command line arguments
    parser = ArgumentParser(
        description="BunkerWeb's backup plugin restore command line interface"
    )

    # Find available backup files
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    backup_file = backups[0] if backups else None
    
    if DEBUG_MODE:
        LOGGER.debug(f"Found {len(backups)} backup files in {BACKUP_DIR}")
        if backups:
            LOGGER.debug(f"Latest backup: {backup_file}")

    # Optional backup file argument with default to latest backup
    parser.add_argument(
        "backup_file", 
        nargs="?", 
        const="default_value", 
        default=backup_file, 
        type=str, 
        help="backup file to restore (default : latest backup)"
    )

    # Parse command line arguments
    args = parser.parse_args()
    
    if DEBUG_MODE:
        LOGGER.debug(f"Parsed arguments: {vars(args)}")

    # Validate backup file selection
    backup_file = Path(args.backup_file) if args.backup_file else None
    
    if DEBUG_MODE:
        LOGGER.debug(f"Selected backup file: {backup_file}")
    
    if not backup_file:
        if backup_file == BACKUP_DIR and not BACKUP_DIR.is_dir():
            LOGGER.error(
                f"Backup directory {BACKUP_DIR} does not exist, "
                f"aborting restore"
            )
            sys_exit(1)

        if not backups:
            LOGGER.error(
                f"No backup found in {BACKUP_DIR}, aborting restore"
            )
            sys_exit(1)

    if not backup_file:
        LOGGER.error("No backup file to restore, aborting restore")
        sys_exit(1)

    if not backup_file.is_file():
        LOGGER.error(
            f"Backup file {backup_file} does not exist, aborting restore"
        )
        sys_exit(1)

    # Create safety backup before restore operation
    LOGGER.info("Backing up the current database before restoring the backup ...")
    
    current_time = datetime.now().astimezone()
    tmp_backup_dir = Path(sep, "tmp", "bunkerweb", "backups")
    
    if DEBUG_MODE:
        LOGGER.debug(f"Creating temporary backup in: {tmp_backup_dir}")
        LOGGER.debug(f"Safety backup timestamp: {current_time}")
    
    tmp_backup_dir.mkdir(parents=True, exist_ok=True)
    db = backup_database(current_time, backup_dir=tmp_backup_dir)

    # Perform the restore operation
    LOGGER.info(f"Restoring backup {backup_file} ...")
    
    if DEBUG_MODE:
        LOGGER.debug(f"Backup file size: {backup_file.stat().st_size} bytes")
        LOGGER.debug(f"Backup file modified: "
                    f"{datetime.fromtimestamp(backup_file.stat().st_mtime)}")
    
    restore_database(backup_file, db)
    
    if DEBUG_MODE:
        LOGGER.debug("Restore command completed successfully")

except SystemExit as se:
    status = se.code
    if DEBUG_MODE:
        LOGGER.debug(f"SystemExit caught with code: {status}")
        
except BaseException as e:
    LOGGER.error(f"Error while executing backup restore command: {e}")
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