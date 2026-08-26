#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os.path import join, sep
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, ensure_backup_dir, LOGGER, update_cache_file

status = 0

try:
    acquire_db_lock()

    # Global parser
    parser = ArgumentParser(description="BunkerWeb's backup plugin save command line interface")

    # Optional directory argument
    parser.add_argument(
        "-d",
        "--directory",
        default=BACKUP_DIR,
        type=str,
        help="directory where to save the backup, default is the one defined in the setting BACKUP_DIRECTORY",
    )

    # Parse args
    args = parser.parse_args()

    directory = Path(args.directory)

    LOGGER.debug(f"Backup directory: {directory}")

    if not directory.is_dir():
        # Create it whichever directory it is. Refusing to create the configured one only
        # worked because `backup-data` happened to have created it at boot: on a fresh install
        # -- or one where that job is held back until the scheduler's first start is over --
        # a manual `bwcli plugin backup save` failed with "does not exist" and nothing told
        # the operator that waiting for the daily job would fix it. The job itself creates the
        # directory unconditionally, so this only aligns the CLI with it.
        LOGGER.info(f"Creating directory {directory} as it does not exist")

    # Always, not only when it is missing: this command runs as root on a package install and
    # the worker that rotates runs as nginx, so the directory has to end up owned by the latter
    # whichever of the two got here first.
    ensure_backup_dir(directory)

    db, _ = backup_database(datetime.now().astimezone(), backup_dir=directory)

    if directory == BACKUP_DIR:
        update_cache_file(db, directory)
except SystemExit as se:
    status = se.code
except BaseException as e:
    LOGGER.error(f"Error while executing backup save command: {e}")
    status = 1
finally:
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
