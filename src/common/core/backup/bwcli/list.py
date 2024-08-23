#!/usr/bin/env python3

from datetime import datetime
from os.path import join, sep
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from utils import BACKUP_DIR, LOGGER

try:
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    message = ""
    if backups:
        message = f"Found {len(backups)} backup{'s' if len(backups) > 1 else ''} in {BACKUP_DIR} :"
        # Show a table with the backups details
        message += "\n+------------+--------------------------+"
        message += "\n|  Database  |           Date           |"
        message += "\n+------------+--------------------------+"
        for backup in backups:
            database = backup.name.split("-")[1]
            date = datetime.strptime("-".join(backup.stem.split("-")[2:]), "%Y-%m-%d_%H-%M-%S").astimezone()
            message += f"\n| {database:<10} | {date.strftime('%Y/%m/%d %H:%M:%S %Z'):<24} |"
        message += "\n+------------+--------------------------+"
    else:
        message = f"No backup found in {BACKUP_DIR}"
    LOGGER.info(message)
except SystemExit as se:
    sys_exit(se.code)
except BaseException as e:
    LOGGER.error(f"Error while executing backup list command: {e}")
    sys_exit(1)
