#!/usr/bin/env python3

from datetime import datetime
from os import getenv
from os.path import join, sep
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import BACKUP_DIR, LOGGER

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "").lower() == "debug"

try:
    if DEBUG_MODE:
        LOGGER.debug(f"Listing backups in directory: {BACKUP_DIR}")
        LOGGER.debug(f"Directory exists: {BACKUP_DIR.exists()}")
    
    # Find and sort backup files by date (newest first)
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    
    if DEBUG_MODE:
        LOGGER.debug(f"Found {len(backups)} backup files")
        for i, backup in enumerate(backups):
            LOGGER.debug(f"Backup {i+1}: {backup.name}")
    
    message = ""
    
    if backups:
        # Create formatted table with backup details
        plural = "s" if len(backups) > 1 else ""
        message = (f"Found {len(backups)} backup{plural} in {BACKUP_DIR} :")
        
        # Table header
        message += "\n+------------+--------------------------+"
        message += "\n|  Database  |           Date           |"
        message += "\n+------------+--------------------------+"
        
        # Table rows with backup information
        for backup in backups:
            # Extract database type from filename (backup-{database}-{date}.zip)
            database = backup.name.split("-")[1]
            
            # Extract and parse date from filename
            date_str = "-".join(backup.stem.split("-")[2:])
            date = datetime.strptime(
                date_str, "%Y-%m-%d_%H-%M-%S"
            ).astimezone()
            
            # Format table row
            formatted_date = date.strftime('%Y/%m/%d %H:%M:%S %Z')
            message += (f"\n| {database:<10} | {formatted_date:<24} |")
            
            if DEBUG_MODE:
                LOGGER.debug(f"Backup: {backup.name}, Database: {database}, "
                           f"Date: {formatted_date}")
        
        # Table footer
        message += "\n+------------+--------------------------+"
    else:
        # No backups found message
        message = f"No backup found in {BACKUP_DIR}"
        
        if DEBUG_MODE:
            LOGGER.debug("No backup files found")
    
    # Log the formatted message
    LOGGER.info(message)
    
    if DEBUG_MODE:
        LOGGER.debug("List command completed successfully")

except SystemExit as se:
    if DEBUG_MODE:
        LOGGER.debug(f"SystemExit caught with code: {se.code}")
    sys_exit(se.code)
    
except BaseException as e:
    LOGGER.error(f"Error while executing backup list command: {e}")
    
    if DEBUG_MODE:
        LOGGER.debug(f"BaseException caught: {type(e).__name__}")
        LOGGER.debug(f"Exception details: {str(e)}")
    
    sys_exit(1)