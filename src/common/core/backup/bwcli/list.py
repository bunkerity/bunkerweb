#!/usr/bin/env python3

from datetime import datetime
from os import getenv
from os.path import join, sep
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import BACKUP_DIR, LOGGER


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


try:
    debug_log(LOGGER, f"Listing backups in directory: {BACKUP_DIR}")
    debug_log(LOGGER, f"Directory exists: {BACKUP_DIR.exists()}")
    
    # Find and sort backup files by date (newest first)
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    
    debug_log(LOGGER, f"Found {len(backups)} backup files")
    for i, backup in enumerate(backups):
        debug_log(LOGGER, f"Backup {i+1}: {backup.name}")
    
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
            
            debug_log(LOGGER, f"Backup: {backup.name}, Database: {database}, "
                     f"Date: {formatted_date}")
        
        # Table footer
        message += "\n+------------+--------------------------+"
    else:
        # No backups found message
        message = f"No backup found in {BACKUP_DIR}"
        
        debug_log(LOGGER, "No backup files found")
    
    # Log the formatted message
    LOGGER.info(message)
    
    debug_log(LOGGER, "List command completed successfully")

except SystemExit as se:
    debug_log(LOGGER, f"SystemExit caught with code: {se.code}")
    sys_exit(se.code)
    
except BaseException as e:
    LOGGER.error(f"Error while executing backup list command: {e}")
    
    debug_log(LOGGER, f"BaseException caught: {type(e).__name__}")
    debug_log(LOGGER, f"Exception details: {str(e)}")
    
    sys_exit(1)