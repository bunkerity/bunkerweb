#!/usr/bin/env python3

from os.path import join, sep
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import BACKUP_DIR, LOGGER, verify_backup_checksum

status = 0

try:
    backups = sorted(BACKUP_DIR.glob("backup-*.zip"))

    if not backups:
        LOGGER.info(f"No backup files found in {BACKUP_DIR}")
        sys_exit(0)

    LOGGER.info(f"Checking {len(backups)} backup file(s) in {BACKUP_DIR} ...")

    failed = 0
    for backup_file in backups:
        if verify_backup_checksum(backup_file):
            LOGGER.info(f"✅ {backup_file.name}: OK")
        else:
            LOGGER.error(f"❌ {backup_file.name}: CHECKSUM MISMATCH")
            failed += 1

    if failed:
        LOGGER.error(f"{failed}/{len(backups)} backup(s) failed checksum verification.")
        sys_exit(1)

    LOGGER.info(f"All {len(backups)} backup(s) passed checksum verification.")
except SystemExit as se:
    status = se.code
except BaseException as e:
    LOGGER.error(f"Error while executing backup check command: {e}")
    status = 1

sys_exit(status)
