The Backup plugin provides an automated backup solution to protect your BunkerWeb data. This feature ensures the safety and availability of your important database by creating regular backups according to your preferred schedule. Backups are stored in a designated location and can be easily managed through both automated processes and manual commands.

**How it works:**

1. Your database is automatically backed up according to the schedule you set (`daily`, `weekly`, `monthly`, or `hanoi`).
2. Backups are stored in a specified directory on your system.
3. Before each backup a disk-space pre-flight check is performed to ensure sufficient free space.
4. Each backup ZIP contains the SQL dump and a SHA-256 checksum file (`.sha256`) for integrity verification.
5. Old backups are automatically rotated based on your retention settings. The `hanoi` schedule uses Towers of Hanoi rotation (24 files, ~85 days of coverage) instead of a simple count.
6. When restoring, the checksum is verified before the live database is touched.
7. You can manually create, list, verify, or restore backups at any time.
8. Before any restore operation, the current state is automatically backed up as a safety measure.

### How to Use

Follow these steps to configure and use the Backup feature:

1. **Enable the feature:** The backup feature is enabled by default. If needed, you can control this with the `USE_BACKUP` setting.
2. **Configure backup schedule:** Choose how often backups should occur by setting the `BACKUP_SCHEDULE` parameter.
3. **Set retention policy:** Specify how many backups to keep using the `BACKUP_ROTATION` setting (ignored when `BACKUP_SCHEDULE=hanoi`).
4. **Define storage location:** Choose where backups will be stored using the `BACKUP_DIRECTORY` setting.
5. **Use CLI commands:** Manage backups manually with the `bwcli plugin backup` commands when needed.

### Configuration Settings

| Setting            | Default                      | Context | Multiple | Description                                                                                                                                                       |
| ------------------ | ---------------------------- | ------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | no       | **Enable Backup:** Set to `yes` to enable automatic backups.                                                                                                      |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | no       | **Backup Frequency:** How often to perform backups. Options: `daily`, `weekly`, `monthly`, or `hanoi` (hourly with Towers of Hanoi rotation, ~85 days coverage). |
| `BACKUP_ROTATION`  | `7`                          | global  | no       | **Backup Retention:** Number of backup files to keep. Ignored when `BACKUP_SCHEDULE=hanoi` (rotation is managed automatically by the Hanoi algorithm).            |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | no       | **Backup Location:** The directory where backup files will be stored.                                                                                             |
| `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE` | `no` | global | no | **Ignore checksum error on restore:** If `yes`, a failed SHA-256 checksum will not abort the restore. Use only as a last resort for partially corrupted backups. |

### Command Line Interface

The Backup plugin provides several CLI commands to manage your backups:

```bash
# List all available backups
bwcli plugin backup list

# Verify SHA-256 checksums of all backups
bwcli plugin backup check

# Create a manual backup
bwcli plugin backup save

# Create a backup in a custom location
bwcli plugin backup save --directory /path/to/custom/location

# Restore from the most recent backup
bwcli plugin backup restore

# Restore from a specific backup file
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Safety First"
    Before any restore operation, the Backup plugin automatically creates a backup of your current database state in a temporary location. This provides an extra safeguard in case you need to revert the restore operation.

!!! info "Integrity Verification"
    Every backup ZIP contains a SHA-256 checksum file alongside the SQL dump. The checksum is automatically verified before any restore. Use `bwcli plugin backup check` to verify all backups at any time.

!!! warning "Database Compatibility"
    The Backup plugin supports SQLite, MySQL/MariaDB, and PostgreSQL databases. Oracle databases are not currently supported for backup and restore operations.

### Example Configurations

=== "Daily Backups with 7-Day Retention"

    Default configuration that creates daily backups and keeps the most recent 7 files:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Towers of Hanoi (~85 days coverage)"

    Runs hourly and applies Towers of Hanoi rotation. Keeps 24 files covering approximately 85 days. `BACKUP_ROTATION` is ignored:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "hanoi"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Weekly Backups with Extended Retention"

    Configuration for less frequent backups with longer retention:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monthly Backups to Custom Location"

    Configuration for monthly backups stored in a custom location:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
