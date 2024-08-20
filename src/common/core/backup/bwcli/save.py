#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os.path import join, sep
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from utils import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, LOGGER

from common_utils import get_timezone  # type: ignore

status = 0

try:
    acquire_db_lock()

    # Global parser
    parser = ArgumentParser(description="BunkerWeb's backup plugin save command line interface")

    # Optional directory argument
    parser.add_argument("-d", "--directory", default=BACKUP_DIR, type=str, help="directory where to save the backup")

    # Parse args
    args = parser.parse_args()

    directory = Path(args.directory)

    LOGGER.debug(f"Backup directory: {directory}")

    if not directory.is_dir():
        if directory == BACKUP_DIR:
            LOGGER.error(f"Backup directory {directory} does not exist")
            sys_exit(1)

        LOGGER.info(f"Creating directory {directory} as it does not exist")
        directory.mkdir(parents=True, exist_ok=True)

    backup_database(datetime.now(get_timezone()), backup_dir=directory)
except SystemExit as se:
    status = se.code
except:
    LOGGER.error(f"Error while executing backup save command :\n{format_exc()}")
    status = 1
finally:
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
